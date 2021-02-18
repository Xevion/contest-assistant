import logging

import discord
from discord.ext import commands
from discord.ext.commands import BucketType, Context, errors

from bot import checks, constants, helpers
from bot.bot import ContestBot
from bot.models import Guild, Period, PeriodStates, Submission

logger = logging.getLogger(__file__)
logger.setLevel(constants.LOGGING_LEVEL)


# TODO: Add command error handling to all commands

class ContestCommandsCog(commands.Cog, name='Contest'):
    """
    Commands related to creating, advancing, and querying contests.
    """

    def __init__(self, bot: ContestBot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx: Context, error: discord.ext.commands.CommandError):
        """
        The event triggered when an error is raised while invoking a command.

        Taken and slightly edited from https://gist.github.com/EvieePy/7822af90858ef65012ea500bcecf1612

        :param error: The context used for command invocation.
        :param ctx: The exception raised.
        """

        # This prevents any commands with local handlers being handled here in on_command_error.
        if hasattr(ctx.command, 'on_error'):
            return

        # This prevents any cogs with an overwritten cog_command_error being handled here.
        cog = ctx.cog
        if cog and cog._get_overridden_method(cog.cog_command_error) is not None:
            return

        ignored = (commands.CommandNotFound,)

        # Allows us to check for original exceptions raised and sent to CommandInvokeError.
        # If nothing is found. We keep the exception passed to on_command_error.
        error = getattr(error, 'original', error)

        # Anything in ignored will return and prevent anything happening.
        if isinstance(error, ignored):
            return

        if isinstance(error, commands.UserInputError):
            message = ''
            if isinstance(error, commands.BadArgument):
                if isinstance(error, commands.ChannelNotFound):
                    message = 'Invalid channel - I couldn\'t find that channel.'
                elif isinstance(error, commands.RoleNotFound):
                    message = 'Invalid role - I couldn\'t find that role'
                elif isinstance(error, commands.ChannelNotReadable):
                    message = 'Invalid channel - I couldn\'t read the contents of that channel.'
                else:
                    message = 'Invalid argument. Please check you entered everything correctly.'
            if isinstance(error, commands.ArgumentParsingError):
                message = 'I couldn\'t read the contents of your arguments properly. Check that you\'ve entered everything properly.'
            if message:
                await ctx.send(embed=helpers.error_embed(message=message))
                return

        if isinstance(error, commands.DisabledCommand):
            await ctx.send(embed=helpers.error_embed(message=f'`{ctx.command}` has been disabled.'))
        elif isinstance(error, commands.NoPrivateMessage):
            try:
                await ctx.send(embed=helpers.error_embed(message=f'`{ctx.command}` can not be used in Private Messages.'))
            except discord.HTTPException:
                pass
        else:
            # All other Errors not returned come here. And we can just print the default TraceBack.
            logger.warning(f'Ignoring exception in command {ctx.command}', exc_info=error)

    @commands.command()
    @commands.guild_only()
    @checks.privileged()
    async def prefix(self, ctx, new_prefix: str):
        """Changes the bot's saved prefix."""

        with self.bot.get_session() as session:
            guild: Guild = session.query(Guild).filter_by(id=ctx.guild.id).first()

            if 1 <= len(new_prefix) <= 2:
                if guild.prefix == new_prefix:
                    return await ctx.send(embed=helpers.error_embed(message=f'The prefix is already `{new_prefix}`.'))
                else:
                    guild.prefix = new_prefix
                    return await ctx.send(embed=helpers.success_embed(message=f'Prefix changed to `{new_prefix}`.'))
            else:
                return await ctx.send(embed=helpers.error_embed(
                        message='Invalid argument. Prefix must be 1 or 2 characters long.'))

    @commands.command()
    @commands.guild_only()
    @checks.privileged()
    async def submission(self, ctx: Context, new_submission: discord.TextChannel) -> None:
        """Changes the bot's saved submission channel."""

        with self.bot.get_session() as session:
            guild: Guild = session.query(Guild).get(ctx.guild.id)

            if guild.submission_channel is not None and guild.submission_channel == new_submission.id:
                await ctx.send(embed=helpers.error_embed(
                        message=f'The submission channel is already set to {new_submission.mention}.'))
            else:
                # TODO: Add channel permissions resetting/migration
                guild.submission_channel = new_submission.id
                await ctx.send(embed=helpers.success_embed(
                        message=f':white_check_mark:  Submission channel changed to {new_submission.mention}.'
                ))

    # noinspection PyDunderSlots,PyUnresolvedReferences
    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(send_messages=True, add_reactions=True, read_message_history=True, manage_roles=True)
    @commands.max_concurrency(1, per=BucketType.guild, wait=True)
    @checks.privileged()
    async def advance(self, ctx: Context, duration: float = None, pingback: bool = True) -> None:
        """
        Advance the state of the current period pertaining to this Guild.

        :param ctx: The context used for command invocation.
        :param duration: If given, the advance command will be repeated once more after the duration (in seconds) has passed.
        :param pingback: Whether or not the user should be pinged back when the duration is passed.
        """
        # TODO: Implement pingback argument
        # TODO: Ensure that permissions for this command are being correctly tested for.
        if duration is not None: assert duration >= 0, "If specified, duration must be more than or equal to zero."

        with self.bot.get_session() as session:
            guild: Guild = session.query(Guild).get(ctx.guild.id)
            period: Period = guild.current_period

            # Handle non-existent or previously completed period in the current guild
            if period is None or not period.active:
                if period is None:
                    overwrite = discord.PermissionOverwrite()
                    overwrite.send_messages = False
                    overwrite.add_reactions = False
                    await self.bot.get_channel(guild.submission_channel).set_permissions(ctx.guild.default_role, overwrite=overwrite)
                    await ctx.send(embed=helpers.success_embed(message='Period created, channel permissions set.'))

                period = Period(guild_id=guild.id)
                session.add(period)
                session.commit()

                guild.current_period = period
                await ctx.send(embed=helpers.success_embed(message='New period started - submissions and voting disabled.'))
            else:
                channel: discord.TextChannel = self.bot.get_channel(guild.submission_channel)
                target_role: discord.Role = ctx.guild.default_role
                # TODO: Research best way to implement contest roles with vagabondit's input

                overwrite = discord.PermissionOverwrite()
                overwrite.send_messages = False
                overwrite.add_reactions = False
                response = 'Permissions unchanged - Period state error.'

                # Handle previous period being completed.
                if period.state == PeriodStates.READY:
                    overwrite.send_messages = True
                    response = 'Period started, submissions allowed. Advance again to pause.'
                # Handle submissions state
                elif period.state == PeriodStates.SUBMISSIONS:
                    response = 'Period paused, submissions disabled. Advance again to start voting.'
                # Handle voting state
                elif period.state == PeriodStates.PAUSED:
                    _guild: discord.Guild = ctx.guild
                    await self.bot.add_voting_reactions(channel=channel, submissions=period.submissions)
                    overwrite.add_reactions = True
                    response = 'Period unpaused, reactions allowed. Advance again to stop voting and finalize the tallying.'
                # Print period submissions
                elif period.state == PeriodStates.VOTING:
                    response = 'Period stopped. Reactions and submissions disabled. Advance again to start a new period.'
                    # TODO: Fetch all submissions related to this period and show a embed

                period.advance_state()
                await channel.set_permissions(target_role, overwrite=overwrite)
                await ctx.send(embed=helpers.success_embed(message=response))

    @advance.error
    async def advance_error(self, error: errors.CommandError, ctx: Context) -> None:
        """
        `advance` command error handling.

        :param error: The error raised while attempting to invoke the command
        :param ctx: The context used for command invocation.
        """
        if isinstance(error, errors.MissingPermissions):
            await ctx.send(embed=helpers.error_embed(
                    message='Check that the bot can actually modify roles, add reactions, see messages and send messages within this channel.'))

    # noinspection PyDunderSlots, PyUnresolvedReferences
    @commands.command()
    @commands.guild_only()
    @checks.privileged()
    async def close(self, ctx: Context) -> None:
        """Closes the current period."""
        with self.bot.get_session() as session:
            guild: Guild = session.query(Guild).get(ctx.guild.id)
            period: Period = guild.current_period

            if period is None or not period.active:
                await ctx.send(embed=helpers.error_embed(message='No period is currently active.'))
            else:
                overwrite = discord.PermissionOverwrite()
                overwrite.send_messages = False
                overwrite.add_reactions = False
                period.deactivate()
                await ctx.send(embed=helpers.success_embed(message='The current period has been closed.'))

    @commands.command()
    @commands.guild_only()
    async def status(self, ctx: Context) -> None:
        """Provides the bot's current state in relation to internal configuration and the server's contest, if active."""
        with self.bot.get_session() as session:
            guild: Guild = session.query(Guild).get(ctx.guild.id)
            period: Period = guild.current_period
            embed = discord.Embed(color=constants.GENERAL_COLOR, title='Status')

            value = f'<#{guild.submission_channel}>' if guild.submission_channel else 'Please set a submission channel.'
            embed.add_field(name='Submission Channel', value=value)

            if period is not None:
                value = 'None' if guild.current_period is None else guild.current_period.state.name.capitalize()
                embed.add_field(name='Status', inline=False, value=f'{value} - {period.permission_explanation()}')
                value = len(period.submissions)
                value = str(value) + '  submission' + ('s' if value > 1 or value == 0 else '')
                embed.add_field(name='Submissions', inline=False, value=value)

            await ctx.send(embed=embed)

    @commands.command()
    @commands.guild_only()
    async def leaderboard(self, ctx: Context, count: int = 10, page: int = 0) -> None:
        """Prints a leaderboard"""
        page = min(page, 0)
        count = max(min(count, 1), 15)

        # TODO: Make interactive and reaction-based
        with self.bot.get_session() as session:
            guild: Guild = session.query(Guild).get(ctx.guild.id)
            if guild.current_period is not None:
                board = session.query(Submission) \
                    .filter_by(period_id=guild.current_period_id) \
                    .order_by(Submission.count.desc()) \
                    .slice(page * count, (page + 1) * count) \
                    .all()

                description = ''
                for i, submission in enumerate(board, start=1):
                    message = self.bot.get_message(guild.submission_channel, submission.id)

                    emote = ''
                    if i == 1: emote = ':trophy:'
                    elif i == 2: emote = ':second_place:'
                    elif i == 3: emote = ':third_place:'

                    description += f'`{str(i).zfill(2)}` {emote + " " if emote else ""}<@{submission.user}> [Jump]({message.jump_url})\n'

                if not description:
                    description = 'No one has submitted anything yet.'

                embed = helpers.general_embed(title='Leaderboard', message=description, timestamp=True)
                embed.set_footer(text='Contest is still in progress...' if guild.current_period.active else 'Contest has finished.')

                await ctx.send(embed=embed)


def setup(bot) -> None:
    bot.add_cog(ContestCommandsCog(bot))
