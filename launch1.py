from bot import TwitchBot, run, settings
run(TwitchBot(**{
    "command_prefix": ["twbeta ", "twb>"] if settings.UseBetaBot else ["twitch ", "Twitch ", "!twitch ", "tw>"],
    "owner_id": 236251438685093889,
    "shard_count": 40,
    "shard_ids": [0,1,2,3,4,5,6,7,8,9]
}))
