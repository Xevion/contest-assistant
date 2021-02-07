import discord as discord


class ContestClient(discord.Client):
    def __init__(self, **options) -> None:
        super().__init__(**options)

    async def on_message(self) -> None:
        pass

    async def on_raw_reaction_add(self, payload) -> None:
        pass

    async def on_raw_reaction_remove(self, payload) -> None:
        pass
