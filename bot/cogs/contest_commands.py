import logging

import discord
from discord.ext import commands
from discord.ext.commands import BucketType, Context, errors

from bot import checks, constants
from bot.bot import ContestBot
from bot.models import Guild, Period, PeriodStates

logger = logging.getLogger(__file__)
logger.setLevel(constants.LOGGING_LEVEL)


class ContestCommandsCog(commands.Cog):
    """
    Manages all commands related to contests.
    """

    def __init__(self, bot: ContestBot) -> None:
        self.bot = bot

    @commands.command()
    @commands.guild_only()
    @checks.privileged()
    async def prefix(self, ctx, new_prefix: str):
        """Changes the bot's saved prefix."""

        with self.bot.get_session() as session:
            guild: Guild = session.query(Guild).filter_by(id=ctx.guild.id).first()

            if 1 <= len(new_prefix) <= 2:
                if guild.prefix == new_prefix:
                    return await ctx.send(f':no_entry_sign:  The prefix is already `{new_prefix}`.')
                else:
                    guild.prefix = new_prefix
                    return await ctx.send(f':white_check_mark:  Prefix changed to `{new_prefix}`.')
            else:
                return await ctx.send(':no_entry_sign: Invalid argument. Prefix must be 1 or 2 characters long.')

    @commands.command()
    @commands.guild_only()
    @checks.privileged()
    async def submission(self, ctx: Context, new_submission: discord.TextChannel) -> None:
        """Changes the bot's saved submission channel."""

        with self.bot.get_session() as session:
            guild: Guild = session.query(Guild).get(ctx.guild.id)

            if guild.submission_channel is not None and guild.submission_channel == new_submission.id:
                await ctx.send(f':no_entry_sign:  The submission channel is already set to {new_submission.mention}.')
            else:
                # TODO: Add channel permissions resetting/migration
                guild.submission_channel = new_submission.id
                await ctx.send(f':white_check_mark:  Submission channel changed to {new_submission.mention}.')

    # noinspection PyDunderSlots,PyUnresolvedReferences
    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(send_messages=True, add_reactions=True, read_message_history=True, manage_roles=True)
    @commands.max_concurrency(1, per=BucketType.guild, wait=True)
    @checks.privileged()
    async def advance(self, ctx: Context, duration: float = None, pingback: bool = True) -> None:
        """
        Advance the state of the current period pertaining to this Guild.

        :param ctx:
        :param duration: If given, the advance command will be repeated once more after the duration (in seconds) has passed.
        :param pingback: Whether or not the user should be pinged back when the duration is passed.
        """
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
                    await ctx.send('Period created, channel permissions set.')

                period = Period(guild_id=guild.id)
                session.add(period)
                session.commit()

                guild.current_period = period
                await ctx.send('New period started - submissions and voting disabled.')
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
                await ctx.send(response)

    @advance.error
    async def advance_error(self, error: errors.CommandError, ctx: Context) -> None:
        if isinstance(error, errors.MissingPermissions):
            await ctx.send(
                    'Check that the bot can actually modify roles, add reactions, see messages and send messages within this channel.')

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
                await ctx.send('No period is currently active.')
            else:
                overwrite = discord.PermissionOverwrite()
                overwrite.send_messages = False
                overwrite.add_reactions = False
                period.deactivate()
                await ctx.send('The current period has been closed.')

    @commands.command()
    @commands.guild_only()
    async def status(self, ctx: Context) -> None:
        """Provides the bot's current state in relation to internal configuration and the server's contest, if active."""
        # TODO: Implement status command
        pass

    @commands.command()
    @commands.guild_only()
    async def leaderboard(self, ctx: Context, count: int = 10, page: int = 0) -> None:
        """Prints a leaderboard"""
        # TODO: Implement leaderboard command
        # TODO: Make interactive and reaction-based
        pass


def setup(bot) -> None:
    bot.add_cog(ContestCommandsCog(bot))
