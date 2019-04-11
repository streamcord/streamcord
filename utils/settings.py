from os import name as osname

UseBetaBot = (osname == 'nt')
Version = "2.4.1"

Token = ""
BetaToken = ""


class BotList:
    DiscordBotsORG = ""
    BotsDiscordGG = ""
    BotsForDiscordCOM = ""
    DiscordBotListCOM = ""


class Twitch:
    Secret = ""
    ClientID = ""
    StreamSecret = ""
    StreamClientID = ""


class Streamlabs:
    Secret = ""
    ClientID = ""


class TRN:
    FortniteAPISecret = ""
    PUBGAPISecret = ""


class Datadog:
    APIKey = ""
    AppKey = ""


class RethinkDB:
    Host = "127.0.0.1"
    Port = 28015


DonatorRoles = []
BannedUsers = []
BotOwners = []
IGDB = ""
DashboardKey = ""
Semaphore = ""
WebhookURL = ""
Crowdin = ""
PerspectiveAPIKey = ""
StreamlabsWebsocketKey = ""
