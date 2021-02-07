import discord
from discord.ext import commands

from contest import checks
from contest.bot import ContestBot


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
                return await ctx.send(f'The prefix is already `{new_prefix}`')
            else:
                await self.bot.db.set_prefix(ctx.guild.id, new_prefix)
                return await ctx.send(f':white_check_mark:  Prefix changed to `{new_prefix}`')
        else:
            return await ctx.send(':no_entry_sign: Invalid argument. Prefix must be 1 or 2 characters long.')

    @commands.command()
    @commands.guild_only()
    @checks.privileged()
    async def submission(self, ctx, new_submission: discord.TextChannel):
        """Changes the bot's saved submission channel."""
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
