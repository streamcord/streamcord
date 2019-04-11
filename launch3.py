from bot import TwitchBot, run, settings
run(TwitchBot(**{
    "command_prefix": ["twbeta ", "twb>"] if settings.UseBetaBot else ["twitch ", "Twitch ", "!twitch ", "tw>"],
    "owner_id": 236251438685093889,
    "shard_count": 40,
    "shard_ids": [20,21,22,23,24,25,26,27,28,29]
}))
