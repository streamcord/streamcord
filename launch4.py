from bot import TwitchBot, run, settings
run(TwitchBot(**{
    "command_prefix": ["twbeta ", "twb>"] if settings.UseBetaBot else ["twitch ", "Twitch ", "!twitch ", "tw>"],
    "owner_id": 236251438685093889,
    "shard_count": 40,
    "shard_ids": [30,31,32,33,34,35,36,37,38,39]
}))
