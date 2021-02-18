import logging
from typing import List

import discord
from discord.ext import commands

from bot import constants, helpers
from bot.bot import ContestBot
from bot.models import Guild, Period, PeriodStates, Submission

logger = logging.getLogger(__file__)
logger.setLevel(constants.LOGGING_LEVEL)


# TODO: Add command error handling to all commands
# TODO: Use embeds in all bot responses
# TODO: Look into migrating from literals to i18n-ish representation of all messages & formatting
# TODO: Contest names
# TODO: Refactor Period into Contest (major)


class ContestEventsCog(commands.Cog):
    """Manages all non-command events related to contests."""

    def __init__(self, bot: ContestBot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user or message.author.bot or not message.guild: return

        with self.bot.get_session() as session:
            guild: Guild = session.query(Guild).get(message.guild.id)

            channel: discord.TextChannel = message.channel
            if channel.id == guild.submission_channel:
                attachments = message.attachments

                # Ensure that the submission contains at least one attachment
                if len(attachments) == 0:
                    await self.bot.reject(message, f':no_entry_sign: {message.author.mention} '
                                                   f'Each submission must contain exactly one image.')
                # Ensure the image contains no more than one attachment
                elif len(attachments) > 1:
                    await self.bot.reject(message, f':no_entry_sign: {message.author.mention} '
                                                   f'Each submission must contain exactly one image.')
                elif guild.current_period is None:
                    await self.bot.reject(message, f':no_entry_sign: {message.author.mention} A period has not been started. '
                                                   f'Submissions should not be allowed at this moment.')
                elif guild.current_period != PeriodStates.SUBMISSIONS:
                    logger.warning(f'Valid submission was sent outside of Submissions in'
                                   f' {channel.id}/{message.id}. Permissions error? Removing.')
                    await message.delete()
                else:
                    attachment = attachments[0]
                    # TODO: Add helper for displaying error/warning messages
                    if attachment.is_spoiler():
                        await self.bot.reject(message, ':no_entry_sign: Attachment must not make use of a spoiler.')
                    elif attachment.width is None:
                        await self.bot.reject(message, ':no_entry_sign: Attachment must be a image or video.')
                    else:
                        last_submission: Submission = session.query(Submission).filter_by(period=guild.current_period,
                                                                                          user=message.author.id).first()
                        if last_submission is not None:
                            # delete last submission
                            submission_msg = await channel.fetch_message(last_submission.id)
                            if submission_msg is None:
                                logger.error(f'Unexpected: submission message {last_submission.id} could not be found.')
                            else:
                                self.bot.expected_msg_deletions.append(submission_msg.id)
                                await submission_msg.delete()
                                logger.info(f'Old submission deleted. {last_submission.id} (Old) -> {message.id} (New)')

                            # Delete the old submission row
                            session.delete(last_submission)

                        # Add the new submission row
                        session.add(Submission(id=message.id, user=message.author.id, period=guild.current_period,
                                               timestamp=message.created_at))
                        logger.info(f'New submission created ({message.id}).')

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent) -> None:
        """Handles submission deletions by the users, moderators or other bots for any reason."""
        await self.bot.wait_until_ready()

        # Ignore messages we delete
        if payload.message_id in self.bot.expected_msg_deletions:
            self.bot.expected_msg_deletions.remove(payload.message_id)
            return

        with self.bot.get_session() as session:
            guild: Guild = session.query(Guild).get(payload.guild_id)
            if payload.channel_id != guild.submission_channel: return

            submission: Submission = session.query(Submission).get(payload.message_id)
            if submission is None:
                logger.error(f'Submission {payload.message_id} could not be deleted from database as it was not found.')
            else:
                author: str = payload.cached_message.author.display_name if payload.cached_message is not None else 'Unknown'
                logger.info(f'Submission {payload.message_id} by {author} deleted by outside source.')
                session.delete(submission)

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(self, payload: discord.RawBulkMessageDeleteEvent) -> None:
        deleted: List[int] = []
        with self.bot.get_session() as session:
            guild: Guild = session.query(Guild).get(payload.guild_id)
            if payload.channel_id == guild.submission_channel:
                for message_id in payload.message_ids:
                    submission: Submission = session.query(Submission).get(message_id)
                    if submission is not None:
                        deleted.append(message_id)
                        session.delete(submission)

        if len(deleted) > 0:
            logger.info(f'{len(deleted)} submissions deleted in bulk message deletion.')
            logger.debug(f'Messages deleted: {", ".join(map(str, deleted))}')

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        # Skip reactions we add ourselves
        if payload.user_id == self.bot.user.id: return

        with self.bot.get_session() as session:
            guild: Guild = session.query(Guild).get(payload.guild_id)
            if payload.channel_id == guild.submission_channel:
                channel: discord.TextChannel = self.bot.get_channel(payload.channel_id)
                message: discord.PartialMessage = channel.get_partial_message(payload.message_id)

                if helpers.is_upvote(payload.emoji):
                    submission: Submission = session.query(Submission).get(payload.message_id)
                    if submission is None:
                        logger.warning(f'Upvote reaction added to message {payload.message_id}, but no Submission found in database.')
                    else:
                        period: Period = submission.period
                        if period.active and period.state == PeriodStates.VOTING:
                            await submission.update(self.bot, message=await message.fetch())
                        else:
                            logger.warning(f'User attempted to add a reaction to a Submission outside '
                                           f'of it\'s Period activity ({period.active}/{period.state}).')
                            await message.remove_reaction(payload.emoji, payload.member)
                else:
                    # Remove the emoji since it's not supposed to be there anyways.
                    # If permissions were setup correctly, only moderators or admins should be able to trigger this.
                    await message.remove_reaction(payload.emoji, payload.member)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        """Deal with reactions we remove or removed manually by users."""
        # Skip reactions we removed ourselves.
        try:
            index = self.bot.expected_react_deletions.index((payload.message_id, payload.emoji.id))
            del self.bot.expected_react_deletions[index]
            logger.debug(f'Skipping expected reaction removal {payload.message_id}.')
            return
        except ValueError:
            pass

        with self.bot.get_session() as session:
            guild: Guild = session.query(Guild).get(payload.guild_id)
            if payload.channel_id == guild.submission_channel and helpers.is_upvote(payload.emoji):
                submission: Submission = session.query(Submission).get(payload.message_id)
                if submission is None:
                    logger.warning(f'Upvote reaction removed from message {payload.message_id}, but no Submission found in database.')
                else:
                    message = await self.bot.fetch_message(payload.channel_id, payload.message_id)
                    await submission.update(self.bot, message=message)

    @commands.Cog.listener()
    async def on_raw_reaction_clear(self, payload: discord.RawReactionActionEvent) -> None:
        """Deal with all emojis being cleared for a specific message. Remove all votes for a given submission and then re-add the bot's."""
        with self.bot.get_session() as session:
            guild: Guild = session.query(Guild).get(payload.guild_id)
            if payload.channel_id == guild.submission_channel:
                submission: Submission = session.query(Submission).get(payload.message_id)
                if submission is None:
                    logger.warning(f'Witnessed reactions removed from message {payload.message_id}, but no Submission found in database.')
                else:
                    submission.votes = []
                    message = self.bot.get_message(payload.channel_id, payload.message_id)
                    await message.add_reaction(self.bot.get_emoji(constants.Emoji.UPVOTE))

    @commands.Cog.listener()
    async def on_raw_reaction_clear_emoji(self, payload: discord.RawReactionClearEmojiEvent) -> None:
        """Deal with a specific emoji being cleared for a message. If it was the upvote, clear votes for the submission and add back the bot's"""
        with self.bot.get_session() as session:
            guild: Guild = session.query(Guild).get(payload.guild_id)
            if payload.channel_id == guild.submission_channel:
                if helpers.is_upvote(payload.emoji):
                    submission: Submission = session.query(Submission).get(payload.message_id)
                    if submission is None:
                        logger.warning(f'Witnessed all upvote reactions removed from message {payload.message_id},'
                                       f' but no Submission found in database.')
                    else:
                        submission.votes = []
                        message = self.bot.get_message(payload.channel_id, payload.message_id)
                        await message.add_reaction(self.bot.get_emoji(constants.Emoji.UPVOTE))


def setup(bot) -> None:
    bot.add_cog(ContestEventsCog(bot))
