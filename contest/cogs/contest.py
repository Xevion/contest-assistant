import logging

import discord
from discord.ext import commands
from discord.ext.commands import Context

from contest import checks, constants
from contest.bot import ContestBot

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
        cur_prefix = await self.bot.db.get_prefix(ctx.guild.id)
        if 1 <= len(new_prefix) <= 2:
            if cur_prefix == new_prefix:
                return await ctx.send(f':no_entry_sign:  The prefix is already `{new_prefix}`.')
            else:
                await self.bot.db.set_prefix(ctx.guild.id, new_prefix)
                return await ctx.send(f':white_check_mark:  Prefix changed to `{new_prefix}`.')
        else:
            return await ctx.send(':no_entry_sign: Invalid argument. Prefix must be 1 or 2 characters long.')

    @commands.command()
    @commands.guild_only()
    @checks.privileged()
    async def submission(self, ctx: Context, new_submission: discord.TextChannel):
        """Changes the bot's saved submission channel."""
        cur_submission = await self.bot.db.get_submission_channel(ctx.guild.id)
        if cur_submission == new_submission.id:
            return await ctx.send(
                f':no_entry_sign:  The submission channel is already set to {new_submission.mention}.')
        else:
            await self.bot.db.set_submission_channel(ctx.guild.id, new_submission.id)
            return await ctx.send(f':white_check_mark:  Submission channel changed to {new_submission.mention}.')

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user or message.author.bot or not message.guild: return
        cur_submission = await self.bot.db.get_submission_channel(message.guild.id)

        channel: discord.TextChannel = message.channel
        if channel.id == cur_submission:
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

                await self.bot.db.add_submission(message.id, channel.guild.id, message.author.id, message.created_at)
                logger.info(f'New submission created ({message.id}).')

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent) -> None:
        """Handles submission deletions by the users, moderators or other bots for any reason."""
        # Ignore messages we delete
        if payload.message_id in expected_deletions:
            expected_deletions.remove(payload.message_id)
            return

        # If the message was cached, check that it's in the correct channel.
        if payload.cached_message is not None:
            cur_submission = await self.bot.db.get_submission_channel(payload.guild_id)
            if payload.cached_message.channel.id != cur_submission:
                return

        cur = await self.bot.db.conn.cursor()
        try:
            await cur.execute('''DELETE FROM submission WHERE id = ? AND guild = ?''',
                              [payload.message_id, payload.guild_id])
            if cur.rowcount > 0:
                author = payload.cached_message.author.display_name if payload.cached_message is not None else 'Unknown'
                logger.info(f'Submission {payload.message_id} by {author} deleted by outside source.')
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
