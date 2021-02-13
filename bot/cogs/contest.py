import logging

import discord
from discord.ext import commands
from discord.ext.commands import Context

from bot import checks, constants
from bot.bot import ContestBot
from bot.models import Guild, Period, PeriodStates, Submission

logger = logging.getLogger(__file__)
logger.setLevel(constants.LOGGING_LEVEL)

expected_deletions = []


class ContestCog(commands.Cog):
    def __init__(self, bot: ContestBot):
        self.bot = bot

    @commands.command()
    @commands.guild_only()
    @checks.privileged()
    async def prefix(self, ctx, new_prefix: str):
        """Changes the bot's saved prefix."""

        with self.bot.get_session() as session:
            guild = session.query(Guild).filter_by(id=ctx.guild.id).first()

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
            guild = session.query(Guild).filter_by(id=ctx.guild.id).first()

            if guild.submission is not None and guild.submission == new_submission.id:
                await ctx.send(f':no_entry_sign:  The submission channel is already set to {new_submission.mention}.')
            else:
                guild.submission_channel = new_submission
                await ctx.send(f':white_check_mark:  Submission channel changed to {new_submission.mention}.')

    @commands.command()
    @commands.guild_only()
    @checks.privileged()
    async def advance(self, ctx: Context, duration: float = None, pingback: bool = True) -> None:
        """
        Advance the state of the current period pertaining to this Guild.

        :param ctx:
        :param duration: If given,
        :param pingback: Whether or not the user should be pinged back when the duration is passed.
        """

        assert duration == -1 or duration >= 0, "Duration must"

        with self.bot.get_session() as session:
            guild: Guild = session.query(Guild).get(ctx.guild.id)
            period: Period = guild.current_period

            # Handle non-existent or previously completed period in the current guild
            if period is None or not period.active:
                session.add(Period(id=ctx.guild.id))

            # Handle previous period being completed.
            elif period.state == PeriodStates.READY:
                # TODO: Open the channel to messages
                pass
            # Handle submissions state
            elif period.state == PeriodStates.SUBMISSIONS:
                # TODO: Close the channel to messages
                return
            # Handle voting state
            elif period.state == PeriodStates.PAUSED:
                # TODO: Add all reactions to every submission
                # TODO: Unlock channel reactions
                # TODO: Close channel submissions
                return
            # Print period submissions
            elif period.state == PeriodStates.VOTING:
                # TODO: Fetch all submissions related to this period
                # TODO: Create new period for Guild at
                return

    @commands.command()
    @commands.guild_only()
    @checks.privileged()
    async def voting(self, ctx: Context, duration: float = None) -> None:
        """Closes submissions and sets up the voting period."""
        if duration < 0:
            await ctx.send('Invalid duration - must be non-negative.')

    @commands.command()
    @commands.guild_only()
    @checks.privileged()
    async def close(self, ctx: Context) -> None:
        """Closes the voting period."""
        pass

    @commands.command()
    @commands.guild_only()
    async def status(self, ctx: Context) -> None:
        """Provides the bot's current state in relation to internal configuration and the server's contest, if active."""
        pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user or message.author.bot or not message.guild: return

        with self.bot.get_session() as session:
            guild = session.query(Guild).get(message.guild.id)
            print(session.query(Guild).all)

            channel: discord.TextChannel = message.channel
            if channel.id == guild.submission:
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
                    last_submission = session.query(Submission).filter_by(id=message.guild.id, user=message.author.id)
                    if last_submission is not None:
                        # delete last submission
                        submission_msg = await channel.fetch_message(last_submission)
                        if submission_msg is None:
                            logger.error(f'Unexpected: submission message {last_submission} could not be found.')
                        else:
                            await submission_msg.delete()
                            logger.info(f'Old submission deleted. {last_submission} (Old) -> {message.id} (New)')

                        # Delete the old submission row
                        session.delete(last_submission)

                    # Add the new submission row
                    session.add(
                            Submission(id=message.id, user=message.author.id, period=guild.current_period, timestamp=message.created_at))
                    logger.info(f'New submission created ({message.id}).')

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent) -> None:
        """Handles submission deletions by the users, moderators or other bots for any reason."""
        await self.bot.wait_until_ready()

        # Ignore messages we delete
        if payload.message_id in expected_deletions:
            expected_deletions.remove(payload.message_id)
            return

        with self.bot.get_session() as session:
            guild: Guild = session.query(Guild).get(payload.guild_id)

            # If the message was cached, check that it's in the correct channel.
            if payload.cached_message is not None and payload.cached_message.channel.id != guild.submission_channel:
                return

            submission = session.query(Submission).get(payload.message_id)
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
        pass

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        pass

    @commands.Cog.listener()
    async def on_raw_reaction_clear(self, payload: discord.RawReactionActionEvent) -> None:
        pass

    @commands.Cog.listener()
    async def on_raw_reaction_clear_emoji(self, payload: discord.RawReactionClearEmojiEvent) -> None:
        pass


def setup(bot) -> None:
    bot.add_cog(ContestCog(bot))
