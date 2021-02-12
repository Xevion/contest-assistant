import logging
from datetime import datetime

import discord
from discord.ext import commands
from discord.ext.commands import Context

from bot import checks, constants
from bot.bot import ContestBot
from bot.db import Period

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
        guild = await self.bot.db.get_guild(ctx.guild.id)

        if 1 <= len(new_prefix) <= 2:
            if guild.prefix == new_prefix:
                return await ctx.send(f':no_entry_sign:  The prefix is already `{new_prefix}`.')
            else:
                await self.bot.db.set_prefix(ctx.guild.id, new_prefix)
                return await ctx.send(f':white_check_mark:  Prefix changed to `{new_prefix}`.')
        else:
            return await ctx.send(':no_entry_sign: Invalid argument. Prefix must be 1 or 2 characters long.')

    @commands.command()
    @commands.guild_only()
    @checks.privileged()
    async def submission(self, ctx: Context, new_submission: discord.TextChannel) -> None:
        """Changes the bot's saved submission channel."""
        guild = await self.bot.db.get_guild(ctx.guild.id)

        if guild.submission is not None and guild.submission == new_submission.id:
            await ctx.send(
                f':no_entry_sign:  The submission channel is already set to {new_submission.mention}.')
        else:
            await self.bot.db.set_submission_channel(ctx.guild.id, new_submission.id)
            await ctx.send(f':white_check_mark:  Submission channel changed to {new_submission.mention}.')

    @commands.command()
    @commands.guild_only()
    @checks.privileged()
    async def submissions(self, ctx: Context, duration: float = None) -> None:
        """Opens up the submissions channel."""
        assert duration == -1 or duration >= 0, "Duration must"

        cur = await self.bot.db.conn.cursor()
        try:
            period = await self.bot.db.get_current_period(ctx.guild.id)

            # Handle non-existent or final-state period
            if period is None:
                new_period = Period(guild=ctx.guild.id, current_state=0, started_at=datetime.now(), voting_at=None, finished_at=None)
                await self.bot.db.new_period(new_period)
            # Handle submissions state
            elif period.current_state == 0:
                await self.bot.db.update_period(period)
                return
            # Handle voting state
            elif period.current_state == 1:
                return
            # Print period submissions
            elif period.current_state == 2:
                # TODO: Fetch all submissions related to this period
                # TODO: Create new period for Guild at
                return
        finally:
            await cur.close()


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
        guild = await self.bot.db.get_guild(message.guild.id)

        channel: discord.TextChannel = message.channel
        if channel.id == guild.submission:
            attachments = message.attachments
            if len(attachments) == 0:
                await message.delete(delay=1)
                warning = await channel.send(
                    f':no_entry_sign: {message.author.mention} Each submission must contain exactly one image.')
                await warning.delete(delay=5)
            elif len(attachments) > 1:
                await message.delete(delay=1)
                warning = await channel.send(
                    f':no_entry_sign: {message.author.mention} Each submission must contain exactly one image.')
                await warning.delete(delay=5)
            else:
                last_submission = await self.bot.db.get_submission(message.guild.id, message.author.id)
                if last_submission is not None:
                    # delete last submission
                    submission_msg = await channel.fetch_message(last_submission)
                    if submission_msg is None:
                        logger.error(f'Unexpected: submission message {last_submission} could not be found.')
                    else:
                        await submission_msg.delete()
                        logger.info(f'Old submission deleted. {last_submission} (Old) -> {message.id} (New)')

                    # Delete the old submission row
                    await self.bot.db.conn.execute('''DELETE FROM submission WHERE id = ?''', [last_submission])
                    await self.bot.db.conn.commit()

                # Add the new submission row
                await self.bot.db.add_submission(message.id, channel.guild.id, message.author.id, message.created_at)
                logger.info(f'New submission created ({message.id}).')

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent) -> None:
        """Handles submission deletions by the users, moderators or other bots for any reason."""
        await self.bot.wait_until_ready()

        # Ignore messages we delete
        if payload.message_id in expected_deletions:
            expected_deletions.remove(payload.message_id)
            return

        # If the message was cached, check that it's in the correct channel.
        if payload.cached_message is not None:
            guild = await self.bot.db.get_guild(payload.guild_id)
            if payload.cached_message.channel.id != guild.submission:
                return

        cur = await self.bot.db.conn.cursor()
        try:
            await cur.execute('''DELETE FROM submission WHERE id = ? AND guild = ?''',
                              [payload.message_id, payload.guild_id])
            if cur.rowcount > 0:
                author = payload.cached_message.author.display_name if payload.cached_message is not None else 'Unknown'
                logger.info(f'Submission {payload.message_id} by {author} deleted by outside source.')
            await self.bot.db.conn.commit()
        finally:
            await cur.close()

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
