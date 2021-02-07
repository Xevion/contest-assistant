from discord.ext import commands


def check_permissions(ctx, perms, *, check=all):
    resolved = ctx.channel.permissions_for(ctx.author)
    return check(getattr(resolved, name, None) == value for name, value in perms.items())


def privileged():
    def predicate(ctx):
        return (ctx.guild is not None and ctx.guild.owner_id == ctx.author.id) \
               or check_permissions(ctx, {'manage_guild': True}) \
               or check_permissions(ctx, {'administrator': True})

    return commands.check(predicate)
