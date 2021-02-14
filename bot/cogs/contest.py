import logging
from typing import List, Tuple

import discord
from discord.ext import commands
from discord.ext.commands import BucketType, Context, errors

from bot import checks, constants
from bot.bot import ContestBot
from bot.models import Guild, Period, PeriodStates, Submission

logger = logging.getLogger(__file__)
logger.setLevel(constants.LOGGING_LEVEL)

expected_msg_deletions: List[int] = []
expected_react_deletions: List[Tuple[int, int]] = []


class ContestCog(commands.Cog):
    def __init__(self, bot: ContestBot):
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
    @commands.cooldown(rate=2, per=5, type=BucketType.guild)
    @commands.max_concurrency(1, per=BucketType.guild, wait=False)
    @checks.privileged()
    async def advance(self, ctx: Context, duration: float = None, pingback: bool = True) -> None:
        """
        Advance the state of the current period pertaining to this Guild.

        :param ctx:
        :param duration: If given, the advance command will be repeated once more after the duration (in seconds) has passed.
        :param pingback: Whether or not the user should be pinged back when the duration is passed.
        """
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
                response = 'Permissions unchanged - Period state error.'

                # Handle previous period being completed.
                if period.state == PeriodStates.READY:
                    overwrite.send_messages = True
                    overwrite.add_reactions = False
                    response = 'Period started, submissions allowed. Advance again to pause.'
                # Handle submissions state
                elif period.state == PeriodStates.SUBMISSIONS:
                    overwrite.send_messages = False
                    overwrite.add_reactions = False
                    response = 'Period paused, submissions disabled. Advance again to start voting.'
                # Handle voting state
                elif period.state == PeriodStates.PAUSED:
                    _guild: discord.Guild = ctx.guild
                    await self.bot.add_voting_reactions(channel=channel, submissions=period.submissions)
                    overwrite.send_messages = False
                    overwrite.add_reactions = True
                    response = 'Period unpaused, reactions allowed. Advance again to stop voting and finalize the tallying.'
                # Print period submissions
                elif period.state == PeriodStates.VOTING:
                    overwrite.send_messages = False
                    overwrite.add_reactions = False
                    response = 'Period stopped. Reactions and submissions disabled. Advance again to start a new period.'
                    # TODO: Fetch all submissions related to this period
                    # TODO: Create new period for Guild at

                period.advance_state()

                await channel.set_permissions(target_role, overwrite=overwrite)
                await ctx.send(response)

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
                period.deactivate()
                await ctx.send('The current period has been closed.')

    @commands.command()
    @commands.guild_only()
    async def status(self, ctx: Context) -> None:
        """Provides the bot's current state in relation to internal configuration and the server's contest, if active."""
        pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user or message.author.bot or not message.guild: return

        with self.bot.get_session() as session:
            guild: Guild = session.query(Guild).get(message.guild.id)

            channel: discord.TextChannel = message.channel
            if channel.id == guild.submission_channel:
                attachments = message.attachments

                # TODO: Do attachment filtering between videos/files/audio etc.

                # Ensure that the submission contains at least one attachment
                if len(attachments) == 0:
                    await message.delete(delay=1)
                    warning = await channel.send(
                            f':no_entry_sign: {message.author.mention} Each submission must contain exactly one image.')
                    await warning.delete(delay=5)
                # Ensure the image contains no more than one attachment
                elif len(attachments) > 1:
                    await message.delete(delay=1)
                    warning = await channel.send(
                            f':no_entry_sign: {message.author.mention} Each submission must contain exactly one image.')
                    await warning.delete(delay=5)
                else:
                    last_submission: Submission = session.query(Submission).filter_by(period=guild.current_period,
                                                                                      user=message.author.id).first()
                    if last_submission is not None:
                        # delete last submission
                        submission_msg = await channel.fetch_message(last_submission.id)
                        if submission_msg is None:
                            logger.error(f'Unexpected: submission message {last_submission.id} could not be found.')
                        else:
                            expected_msg_deletions.append(submission_msg.id)
                            await submission_msg.delete()
                            logger.info(f'Old submission deleted. {last_submission.id} (Old) -> {message.id} (New)')

                        # Delete the old submission row
                        session.delete(last_submission)

                    # Add the new submission row
                    session.add(Submission(id=message.id, user=message.author.id,
                                           period=guild.current_period, timestamp=message.created_at))
                    logger.info(f'New submission created ({message.id}).')

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent) -> None:
        """Handles submission deletions by the users, moderators or other bots for any reason."""
        await self.bot.wait_until_ready()

        # Ignore messages we delete
        if payload.message_id in expected_msg_deletions:
            expected_msg_deletions.remove(payload.message_id)
            return

        with self.bot.get_session() as session:
            guild: Guild = session.query(Guild).get(payload.guild_id)

            # If the message was cached, check that it's in the correct channel.
            if payload.cached_message is not None and payload.cached_message.channel.id != guild.submission_channel:
                return

            submission: Submission = session.query(Submission).get(payload.message_id)
            if submission is None:
                logger.error(f'Submission {payload.message_id} could not be deleted from database as it was not found.')
            else:
                author: str = payload.cached_message.author.display_name if payload.cached_message is not None else 'Unknown'
                logger.info(f'Submission {payload.message_id} by {author} deleted by outside source.')
                session.delete(submission)

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(self, payload: discord.RawBulkMessageDeleteEvent) -> None:
        pass

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        # Skip reactions we add ourselves
        if payload.user_id == self.bot.user.id: return

        with self.bot.get_session() as session:
            guild: Guild = session.query(Guild).get(payload.guild_id)
            if payload.channel_id == guild.submission_channel:
                channel: discord.TextChannel = self.bot.get_channel(payload.channel_id)
                message: discord.PartialMessage = channel.get_partial_message(payload.message_id)
                if payload.emoji.id != constants.Emoji.UPVOTE:
                    await message.remove_reaction(payload.emoji, payload.member)
                else:
                    submission: Submission = session.query(Submission).get(payload.message_id)
                    if submission is None:
                        logger.warning(f'Upvote reaction added to message {payload.message_id}, but no Submission found in database.')
                    else:
                        submission.increment()
                        # Make sure our reaction exists, verify vote count
                        self_reacted = await submission.verify(await message.fetch(), self.bot.user)
                        if not self_reacted:
                            await message.add_reaction(self.bot.get_emoji(constants.Emoji.UPVOTE))

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        """Deal with reactions we remove or removed manually by users."""
        # Skip reactions we removed ourselves.
        try:
            index = expected_react_deletions.index((payload.message_id, payload.emoji.id))
            del expected_react_deletions[index]
            logger.debug(f'Skipping expected reaction removal {payload.message_id}.')
            return
        except ValueError:
            pass

        with self.bot.get_session() as session:
            guild: Guild = session.query(Guild).get(payload.guild_id)
            if payload.channel_id == guild.submission_channel and payload.emoji.id == constants.Emoji.UPVOTE:
                submission: Submission = session.query(Submission).get(payload.message_id)
                if submission is None:
                    logger.warning(f'Upvote reaction removed from message {payload.message_id}, but no Submission found in database.')
                else:
                    submission.decrement()

                    # Get the actual number of votes from the message
                    channel: discord.TextChannel = self.bot.get_channel(payload.channel_id)
                    message: discord.Message = await channel.fetch_message(payload.message_id)
                    self_reacted = await submission.verify(await message.fetch(), self.bot.user)

                    # Make sure our reaction exists
                    if not self_reacted:
                        await message.add_reaction(self.bot.get_emoji(constants.Emoji.UPVOTE))

    @commands.Cog.listener()
    async def on_raw_reaction_clear(self, payload: discord.RawReactionActionEvent) -> None:
        pass

    @commands.Cog.listener()
    async def on_raw_reaction_clear_emoji(self, payload: discord.RawReactionClearEmojiEvent) -> None:
        pass


def setup(bot) -> None:
    bot.add_cog(ContestCog(bot))
