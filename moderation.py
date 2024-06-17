import guilded, json, re2, time, jsonschema, requests, base64, imageio, math, random
from guilded.ext import commands
from core.database import *
from quart import request, jsonify, Response
from psycopg.rows import dict_row
from quart_cors import route_cors
from core.checks_api import *
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
from io import BufferedIOBase, BytesIO, IOBase
from aiohttp import ClientSession
from tools.db_funcs import addAuditLog, getServerSettings, getServerRules
from pathlib import Path
from tools.IDs import generateSnowflakeFromIDType
from tools.reusable_chat_messages import messageWarning
from tools import footer_messages
from tools.help_generation import command

#TODO: Finish Routes
#TODO: Finish punishments
class Moderation(commands.Cog):
    def __init__(self,bot):
        self.bot = bot

    def register_routes(self, app):

        @app.route("/moderation/<server_id>/getRules", methods=["GET"])
        @route_cors(allow_headers=["content-type"], allow_methods=["GET"], allow_origin="*")
        async def GetModerationRules(server_id: str):
            return
            try:
                data = await getServerSettings(server_id)['moderation_rules']
            except:
                return jsonify({"error": "An internal error occurred."}), 404
            return jsonify(data["moderation_rules"])
        
        @app.route("/moderation/<server_id>/setRules", methods=["POST"])
        @route_cors(allow_headers=["content-type"], allow_methods=["POST"], allow_origin="*")
        async def SetModerationRules(server_id: str):
            return
    
    async def moderateMessage(self, message, messageBefore=None):
        server_data_DB = await getServerRules(message.server.id)
        if not message.author.id == self.bot.user.id and (await getServerSettings(message.server.id))["moderation_toggle"] == True and server_data_DB and not message.author.is_owner():
            for rule in server_data_DB:
                if rule["enabled"] and re2.search(rule["rule"], message.content):
                    if rule:
                        messageToReply = rule["custom_message"] if rule["custom_message"] else "Your message has been flagged because it violates this server's automod rules. If you believe this is a mistake, please contact a moderator."
                        reason = rule["custom_reason"] if rule["custom_reason"] else f"This user has violated the server's automod rules. ({rule['rule']})"
                        if rule["punishment"][0] == "warn": #TODO: add database warnings
                            if messageBefore and message.content[re2.search(rule["rule"], message.content).start():re2.search(rule["rule"], message.content).end()] in messageBefore.content:
                                return
                            await messageWarning(message, messageToReply)
                            await addAuditLog(message.server.id, self.bot.user.id, "warn", reason, message.author.id, extraData={"automation": "moderation", "rule": rule['rule'], "messageID": message.id})
                        elif rule["punishment"][0] == "kick":
                            await messageWarning(message, messageToReply)
                            await addAuditLog(message.server.id, self.bot.user.id, "kick", reason, message.author.id, extraData={"automation": "moderation", "rule": rule['rule'], "messageID": message.id})
                            await message.delete()
                            await message.author.kick()
                        elif rule["punishment"][0] == "ban":
                            await messageWarning(message, messageToReply)
                            await addAuditLog(message.server.id, self.bot.user.id, "ban", reason, message.author.id, extraData={"automation": "moderation", "rule": rule['rule'], "messageID": message.id})
                            await message.delete()
                            await message.author.ban(reason=reason)
                        elif rule["punishment"][0] == "mute": #TODO: fix mutes
                            await messageWarning(message, messageToReply)
                            await addAuditLog(message.server.id, self.bot.user.id, "mute", reason, message.author.id, extraData={"automation": "moderation", "rule": rule['rule'], "messageID": message.id})
                            await message.delete()
                        elif rule["punishment"][0] == "delete":
                            await messageWarning(message, messageToReply)
                            await addAuditLog(message.server.id, self.bot.user.id, "delete", reason, message.author.id, extraData={"automation": "moderation", "rule": rule['rule'], "messageID": message.id})
                            await message.delete()
                        break

    @commands.Cog.listener()
    async def on_message(self, event: guilded.MessageEvent):
        await self.moderateMessage(event.message)
        
    @commands.Cog.listener()
    async def on_message_update(self, event: guilded.MessageUpdateEvent):
        await self.moderateMessage(event.after, messageBefore=event.before)

    @command("Rules", "rules", "Moderation", "Add, remove, or list automod rules.", "rules [add/remove/clear/list]", "Add, remove, or list automod rules.", aliases=['rules', 'rule'], subCommands=[{"name": "add", "description": "Add a new automod rule.", "usage": "rules add <rule>", "aliases": ["add", "create"], "hidden": False}, {"name": "remove", "description": "Remove an automod rule.", "usage": "rules remove <ruleID/rule>", "aliases": ["remove", "delete"], "hidden": False}, {"name": "clear", "description": "Clear all automod rules.", "aliases": ["clear"], "usage": "rules clear", "hidden": False}, {"name": "list", "description": "List all automod rules.", "usage": "rules list", "aliases": ["list", "get"], "hidden": False}])
    @commands.command(aliases=["rule"])
    async def rules(self, ctx, *, rules=""):
        arguments = rules.split(" ")
        author = ctx.author
        guild = ctx.guild
        if arguments[0] in ["add", "create"]:
            punishment = arguments[2] if len(arguments) > 2 else "delete"
            amount = arguments[3] if len(arguments) > 3 else 1
            rules = arguments[1] 
            ruleID = generateSnowflakeFromIDType("moderation_rules")
            if punishment in ["warn", "delete"] and not (author.is_owner() or author.server_permissions.administrator or author.server_permissions.manage_messages):
                embed = guilded.Embed(title="Permission Denied", description="You do not have permission to add this punishment!", color=guilded.Color.red())
                embed.set_footer(text=footer_messages.getFooterMessage())
                return await ctx.reply(embed=embed)
            elif punishment in ["kick"] and not (author.is_owner() or author.server_permissions.administrator or author.server_permissions.kick_members or author.server_permissions.ban_members):
                embed = guilded.Embed(title="Permission Denied", description="You do not have permission to add this punishment!", color=guilded.Color.red())
                embed.set_footer(text=footer_messages.getFooterMessage())
                return await ctx.reply(embed=embed)
            elif punishment in ["ban"] and not (author.is_owner() or author.server_permissions.administrator or author.server_permissions.ban_members):
                embed = guilded.Embed(title="Permission Denied", description="You do not have permission to add this punishment!", color=guilded.Color.red())
                embed.set_footer(text=footer_messages.getFooterMessage())
                return await ctx.reply(embed=embed)
            elif punishment in ["mute"] and not (author.is_owner() or author.server_permissions.administrator  or author.server_permissions.manage_roles):
                embed = guilded.Embed(title="Permission Denied", description="You do not have permission to add this punishment!", color=guilded.Color.red())
                embed.set_footer(text=footer_messages.getFooterMessage())
                return await ctx.reply(embed=embed)
            db_pool = await db_connection.db_connection()
            async with db_pool.connection() as conn:
                cursor = conn.cursor(row_factory=dict_row)
                updated = await cursor.execute("""INSERT INTO rules (rule, punishment, author_id, id, server_id, enabled, deleted) SELECT %s, %s,%s, %s, %s, %s, %s WHERE NOT EXISTS (SELECT 1 FROM rules WHERE rule = %s AND server_id = %s AND deleted = false)""", (rules, json.dumps([punishment, amount]), author.id, ruleID , guild.id, True, False,  rules, guild.id))
                await conn.commit()
            if updated.rowcount > 0:
                embed = guilded.Embed(title="Rule Added", description=f"Rule: {rules}\nPunishment: {punishment.capitalize()}\nAmount: {amount}\nCreator: {author.mention}\n Rule ID: {ruleID}", color=guilded.Color.green())
                await addAuditLog(guild.id, author.id, "automod_rule_add", f"User {author.name} added automod rule: {rules}", author.id, extraData={"rule": rules, "ruleID": ruleID})
            else:
                embed = guilded.Embed(title="Rule Not Added", description=f"This rule ({rules}) has not been added because it already exists.", color=guilded.Color.gilded())
            embed.set_footer(text=footer_messages.getFooterMessage())
            return await ctx.reply(embed=embed)
        elif arguments[0] in ["remove", "delete"]:
            db_pool = await db_connection.db_connection()
            async with db_pool.connection() as conn:
                cursor = conn.cursor(row_factory=dict_row)
                updated = await cursor.execute("""UPDATE rules SET deleted = true WHERE server_id = %s and (id = %s or rule = %s) and deleted = false RETURNING *""", (guild.id, arguments[1], arguments[1]))
                updatedRules = await cursor.fetchone()
                if updatedRules:
                    if updatedRules["punishment"][0] in ["warn", "delete"] and not (author.is_owner() or author.server_permissions.administrator or author.server_permissions.manage_messages):
                        await conn.rollback()
                        embed = guilded.Embed(title="Permission Denied", description="You do not have permission to remove this punishment!", color=guilded.Color.red())
                        embed.set_footer(text=footer_messages.getFooterMessage())
                        return await ctx.reply(embed=embed)
                    elif updatedRules["punishment"][0] in ["kick"] and not (author.is_owner() or author.server_permissions.administrator or author.server_permissions.kick_members or author.server_permissions.ban_members):
                        await conn.rollback()
                        embed = guilded.Embed(title="Permission Denied", description="You do not have permission to remove this punishment!", color=guilded.Color.red())
                        embed.set_footer(text=footer_messages.getFooterMessage())
                        return await ctx.reply(embed=embed)
                    elif updatedRules["punishment"][0] in ["ban"] and not (author.is_owner() or author.server_permissions.administrator or author.server_permissions.ban_members):
                        await conn.rollback()
                        embed = guilded.Embed(title="Permission Denied", description="You do not have permission to remove this punishment!", color=guilded.Color.red())
                        embed.set_footer(text=footer_messages.getFooterMessage())
                        return await ctx.reply(embed=embed)
                    elif updatedRules["punishment"][0] in ["mute"] and not (author.is_owner() or author.server_permissions.administrator or author.server_permissions.manage_roles):
                        await conn.rollback()
                        embed = guilded.Embed(title="Permission Denied", description="You do not have permission to remove this punishment!", color=guilded.Color.red())
                        embed.set_footer(text=footer_messages.getFooterMessage())
                        return await ctx.reply(embed=embed)
                    await conn.commit()
            if updated.rowcount > 0:
                try:
                    creator = (await guild.fetch_member(updatedRules["author_id"])).mention
                except:
                    creator = await self.bot.fetch_user(updatedRules["author_id"])
                    creator = f"{creator.display_name} ({creator.id})"
                embed = guilded.Embed(title="Rule Removed", description=f"Rule: {updatedRules['rule']}\nPunishment: {updatedRules['punishment'][0].capitalize()}\nAmount: {updatedRules['punishment'][1]}\nCreator: {creator}\n Rule ID: {updatedRules['id']}\nDescription: {updatedRules['description']}", color=guilded.Color.green())
                await addAuditLog(guild.id, author.id, "automod_rule_remove", f"User {author.name} removed automod rule: {updatedRules['rule']}", author.id, extraData={"rule": updatedRules['rule'], "ruleID": updatedRules['id']})
            else:
                embed = guilded.Embed(title="Rule Not Found", description=f"This rule ({arguments[1]}) has not been removed because it does not exist.", color=guilded.Color.gilded())
            embed.set_footer(text=footer_messages.getFooterMessage())
            return await ctx.send(embed=embed)
        elif arguments[0] in ["clear"]:
            db_pool = await db_connection.db_connection()
            async with db_pool.connection() as conn:
                cursor = conn.cursor(row_factory=dict_row)
                updated = await cursor.execute("""UPDATE rules SET deleted = true WHERE server_id = %s and deleted = false RETURNING *""", (guild.id,))
                updatedRules = await cursor.fetchall()
                wordCount, description, creatorCache = 0, "", {}
                for i in updatedRules:
                    if (i["punishment"][0] in ["warn", "delete"] and not (author.is_owner() or author.server_permissions.administrator or author.server_permissions.manage_messages)) or (i["punishment"][0] in ["kick"] and not (author.is_owner() or author.server_permissions.administrator or author.server_permissions.kick_members or author.server_permissions.ban_members) or (i["punishment"][0] in ["ban"] and not (author.is_owner() or author.server_permissions.administrator or author.server_permissions.ban_members)) or (i["punishment"][0] in ["mute"] and not (author.is_owner() or author.server_permissions.administrator or author.server_permissions.manage_roles))):
                        await conn.rollback()
                        embed = guilded.Embed(title="Permission Denied", description="You do not have permission to clear these punishments!", color=guilded.Color.red())
                        break
                    if not i["author_id"] in creatorCache:
                        try:
                            creatorCache[i["author_id"]] = (await guild.fetch_member(i["author_id"])).mention
                        except:
                            creator = await self.bot.fetch_user(i["author_id"])
                            creatorCache[i["author_id"]] = f"{creator.display_name} ({creator.id})"
                    ruleText = f"***Rule: {i['rule']}***\nPunishment: {i['punishment'][0].capitalize()}\nAmount: {i['punishment'][1]}\nCreator: {creatorCache[i['author_id']]}\n Rule ID: {i['id']}\nDescription: {i['description']}\nEnabled: {i['enabled']}\nCustom Message: {i['custom_message']}\nCustom Reason: {i['custom_reason']}\n\n"
                    wordCount += len(ruleText)
                    if wordCount > 2000:
                        embed = guilded.Embed(title="Rules Cleared", description=description, color=guilded.Color.green())
                        embed.set_footer(text=footer_messages.getFooterMessage())
                        await ctx.send(embed=embed)
                        description, wordCount = ruleText, len(ruleText)
                    else:
                        description += ruleText
                if len(description) > 0:
                    embed = guilded.Embed(title="Rules Cleared", description=description, color=guilded.Color.green())
                await conn.commit()
            if not updated.rowcount > 0:
                await addAuditLog(guild.id, author.id, "automod_rule_clear", f"User {author.name} cleared automod rules.", author.id, extraData={"ruleID": [i['id'] for i in updatedRules]})
                embed = guilded.Embed(title="No Rules Found", description=f"I couldn't find any rules to clear!", color=guilded.Color.gilded())
            if 'embed' in locals():
                embed.set_footer(text=footer_messages.getFooterMessage())
                return await ctx.send(embed=embed)
        elif arguments[0] in ["list", "get", ""]:
            if author.is_owner() or author.server_permissions.administrator or author.server_permissions.manage_messages or author.server_permissions.manage_roles or author.server_permissions.kick_members or author.server_permissions.ban_members:
                rules = await getServerRules(guild.id)
                if not rules:
                    em = guilded.Embed(title="Rules", description="No rules found!", color=guilded.Color.green())
                    em.set_footer(text=footer_messages.getFooterMessage())
                    return await ctx.send(embed=em)
                wordCount, description, creatorCache = 0, "", {}
                for i in rules:
                    if not i["author_id"] in creatorCache:
                        try:
                            creatorCache[i["author_id"]] = (await guild.fetch_member(i["author_id"])).mention
                        except:
                            creator = await self.bot.fetch_user(i["author_id"])
                            creatorCache[i["author_id"]] = f"{creator.display_name} ({creator.id})"
                    ruleText = f"***Rule: {i['rule']}***\nPunishment: {i['punishment'][0].capitalize()}\nAmount: {i['punishment'][1]}\nCreator: {creatorCache[i['author_id']]}\n Rule ID: {i['id']}\nDescription: {i['description']}\nEnabled: {i['enabled']}\nCustom Message: {i['custom_message']}\nCustom Reason: {i['custom_reason']}\n\n"
                    wordCount += len(ruleText)
                    if wordCount > 2000:
                        em = guilded.Embed(title="Rules", description=description, color=guilded.Color.green())
                        em.set_footer(text=footer_messages.getFooterMessage())
                        await ctx.send(embed=em)
                        description, wordCount = ruleText, len(ruleText)
                    else:
                        description += ruleText
                if wordCount > 0:
                    em = guilded.Embed(title="Rules", description=description, color=guilded.Color.green())
                await addAuditLog(guild.id, author.id, "automod_rule_list", f"User {author.name} listed automod rules.", author.id)
            else:
                em = guilded.Embed(title="Permission Denied", description="You do not have permission to view this information!", color=guilded.Color.red())
            if em:
                em.set_footer(text=footer_messages.getFooterMessage())
                await ctx.send(embed=em)

    @command("Moderation", "moderation", "Moderation", "Enable, disable, or toggle moderation.", "moderation [enable/disable/toggle/status]", "Enable, disable, or toggle moderation.", aliases=['moderation'], subCommands=[{"name": "enable", "description": "Enable moderation.", "usage": "moderation enable", "aliases": ["enable", "on"], "hidden": False}, {"name": "disable", "description": "Disable moderation.", "usage": "moderation disable", "aliases": ["disable", "off"], "hidden": False}, {"name": "toggle", "description": "Toggle moderation.", "usage": "moderation toggle", "aliases": ["toggle"], "hidden": False}, {"name": "status", "description": "Get the status of moderation.", "usage": "moderation status", "aliases": ["status", "info"], "hidden": False}])
    @commands.command()
    async def moderation(self, ctx, *, arguments=""):
        arguments = arguments.split(" ")
        author = ctx.author
        guild = ctx.guild
        if arguments[0] in ["enable", "on"]:
            if not(author.is_owner() or author.server_permissions.administrator):
                embed = guilded.Embed(title="Permission Denied", description="You do not have permission to enable moderation!", color=guilded.Color.red())
                embed.set_footer(text=footer_messages.getFooterMessage())
                return await ctx.reply(embed=embed)
            db_pool = await db_connection.db_connection()
            async with db_pool.connection() as conn:
                cursor = conn.cursor(row_factory=dict_row)
                await cursor.execute("""UPDATE server_settings as newversion SET moderation_toggle = true FROM server_settings AS oldversion WHERE newversion.server_id = %s RETURNING oldversion.moderation_toggle""", (guild.id,))
                await conn.commit()
                previousValue = (await cursor.fetchone())["moderation_toggle"]
            if previousValue == True:
                embed = guilded.Embed(title="Moderation", description="Moderation is already enabled!", color=guilded.Color.gilded())
            else:
                embed = guilded.Embed(title="Moderation", description="Moderation has been enabled!", color=guilded.Color.green())
                await addAuditLog(guild.id, author.id, "moderation_enable", f"User {author.name} has enabled moderation.", author.id)
            embed.set_footer(text=footer_messages.getFooterMessage())
            await ctx.send(embed=embed)
        elif arguments[0] in ["disable", "off"]:
            if not(author.is_owner() or author.server_permissions.administrator):
                embed = guilded.Embed(title="Permission Denied", description="You do not have permission to disable moderation!", color=guilded.Color.red())
                return await ctx.reply(embed=embed)
            db_pool = await db_connection.db_connection()
            async with db_pool.connection() as conn:
                cursor = conn.cursor(row_factory=dict_row)
                await cursor.execute("""UPDATE server_settings as newversion SET moderation_toggle = false FROM server_settings AS oldversion WHERE newversion.server_id = %s RETURNING oldversion.moderation_toggle""", (guild.id,))
                await conn.commit()
                previousValue = (await cursor.fetchone())["moderation_toggle"]
            if previousValue == False:
                embed = guilded.Embed(title="Moderation", description="Moderation is already disabled!", color=guilded.Color.gilded())
            else:
                embed = guilded.Embed(title="Moderation", description="Moderation has been disabled!", color=guilded.Color.green())
                await addAuditLog(guild.id, author.id, "moderation_disable", f"User {author.name} has disabled moderation.", author.id)
            embed.set_footer(text=footer_messages.getFooterMessage())
            await ctx.send(embed=embed)
        elif arguments[0] in ["toggle"]:
            if not(author.is_owner() or author.server_permissions.administrator):
                embed = guilded.Embed(title="Permission Denied", description="You do not have permission to toggle moderation!", color=guilded.Color.red())
                embed.set_footer(text=footer_messages.getFooterMessage())
                return await ctx.reply(embed=embed)
            db_pool = await db_connection.db_connection()
            async with db_pool.connection() as conn:
                cursor = conn.cursor(row_factory=dict_row)
                await cursor.execute("""UPDATE server_settings as newversion SET moderation_toggle = NOT newversion.moderation_toggle FROM server_settings AS oldversion WHERE newversion.server_id = %s RETURNING oldversion.moderation_toggle""", (guild.id,))
                await conn.commit()
                previousValue = (await cursor.fetchone())["moderation_toggle"]
            if previousValue == False:
                embed = guilded.Embed(title="Moderation", description="Moderation has been enabled!", color=guilded.Color.green())
                await addAuditLog(guild.id, author.id, "moderation_enable", f"User {author.name} has enabled moderation.", author.id)
            else:
                embed = guilded.Embed(title="Moderation", description="Moderation has been disabled!", color=guilded.Color.green())
                await addAuditLog(guild.id, author.id, "moderation_disable", f"User {author.name} has disabled moderation.", author.id)
            embed.set_footer(text=footer_messages.getFooterMessage())
            await ctx.send(embed=embed)
        elif arguments[0] in ["status", "info", ""]:
            if author.is_owner() or author.server_permissions.administrator or author.server_permissions.manage_messages or author.server_permissions.manage_roles or author.server_permissions.kick_members or author.server_permissions.ban_members:
                serverData = await getServerSettings(guild.id)
                description = ""
                if serverData["moderation_toggle"]:
                    description += "Enabled :white_check_mark:\n"
                else:
                    description += "Disabled :x:\n"
                em = guilded.Embed(title="Moderation", description=description, color=guilded.Color.green())
            else:
                em = guilded.Embed(title="Permission Denied", description="You do not have permission to view this information!", color=guilded.Color.red())
            em.set_footer(text=footer_messages.getFooterMessage())
            await ctx.send(embed=em)

    @command("Purge", "purge", "Moderation", "Purge a set of messages.", "purge <number (<=98)>", "Purges an amount of messages from the current channel. (Purge amount must be less than or equal to 98)", aliases=['purge'])
    @commands.command()
    async def purge(self, ctx, *, amount, private:bool=True):
        if (ctx.author.is_owner() or ctx.author.server_permissions.administrator or ctx.author.server_permissions.manage_messages):
            try:
                amount = int(amount)+2
            except:
                embed = guilded.Embed(title="Invalid Amount", description="The amount of messages to delete must be a number.", color=guilded.Color.red())
                embed.set_footer(text=footer_messages.getFooterMessage())
                return await ctx.reply(embed=embed)
            if not amount-2 <= 98:
                embed = guilded.Embed(title="Invalid Amount", description="The amount of messages to delete must be less than 98.", color=guilded.Color.red())
                embed.set_footer(text=footer_messages.getFooterMessage())
                return await ctx.reply(embed=embed)
            else:
                messages = await ctx.channel.history(limit=amount, include_private=private)
                for message in messages:
                    await message.delete()
                embed = guilded.Embed(title="Purge", description=f"{amount-2} messages have been deleted!", color=guilded.Color.green())
                embed.set_footer(text=footer_messages.getFooterMessage())
                return await ctx.send(embed=embed, delete_after=5)
        else:
            embed = guilded.Embed(title="Permission Denied", description="You do not have permission to user this!", color=guilded.Color.red())
        embed.set_footer(text=footer_messages.getFooterMessage())
        return await ctx.reply(embed=embed)
        print(amount)

def setup(bot):
    bot.add_cog(Moderation(bot))
