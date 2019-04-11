from bot import TwitchBot, run, settings
run(TwitchBot(**{
    "command_prefix": ["twbeta ", "twb>"] if settings.UseBetaBot else ["twitch ", "Twitch ", "!twitch ", "tw>"],
    "owner_id": 236251438685093889,
    "shard_count": 40,
    "shard_ids": [10,11,12,13,14,15,16,17,18,19]
}))
