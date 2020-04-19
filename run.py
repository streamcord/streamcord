import argparse
import os
import sys

from dotenv import load_dotenv

# Create cli arguments
parser = argparse.ArgumentParser()
parser.add_argument(
    '-e', '--env',
    default='.env',
    metavar='ENV_FILE',
    help='Choose the environment file')
parser.add_argument(
    '-d', '--disable-features',
    action='extend',
    nargs='+',
    metavar='FEATURES',
    help='List of features to disable. Possible values: '
         'crowdin-build, crowdin-pull, legacy-notifs, live-role-backlog, web-server')
parser.add_argument(
    '--shard-count',
    default=1,
    type=int,
    metavar='NUM',
    help='The total number of shards the bot should connect to Discord with')
parser.add_argument(
    '--shard-ids',
    action='extend',
    nargs='+',
    type=int,
    metavar='IDS',
    help='Zero-indexed shard IDs the bot should connect to Discord with')
parser.add_argument(
    '--shards-per-cluster',
    default=5,
    type=int,
    metavar='NUM',
    help='The amount of shards per cluster')
parser.add_argument(
    '--cluster-index',
    type=int,
    metavar='INDEX',
    help='The offset of shards the bot should connect to Discord with')

# Argument validation
args = parser.parse_args()
if args.shard_ids and args.cluster_index:
    print('The cluster-index and shard-ids options cannot be used together')
    sys.exit(1)
if args.cluster_index is not None:
    if args.shards_per_cluster < 1:
        print('Shards per cluster cannot be less than 1')
        sys.exit(1)
    if args.cluster_index < 1:
        print('Cluster index cannot be less than 1')
        sys.exit(1)
    if args.shards_per_cluster > args.shard_count:
        print(f'The maximum amount of shards per cluster can be {args.shard_count}')
        sys.exit(1)
    if args.shard_count % args.shards_per_cluster != 0:
        print('Invalid shard mapping (shard-count % shards-per-cluster does not equal 0)')
        sys.exit(1)
    sid = args.shards_per_cluster * args.cluster_index
    if sid > args.shard_count:
        m_val = int(args.shard_count / args.shards_per_cluster)
        print(f'Cluster {args.cluster_index} is invalid. The highest cluster index can be {m_val}')
        sys.exit(1)
    args.shard_ids = list(range(sid - args.shards_per_cluster, sid))
else:
    if args.shard_ids is None:
        args.shard_ids = [0]
    if args.shard_count < 1:
        print('Shard count cannot be less than 1')
        sys.exit(1)
    if any([x for x in args.shard_ids if x < 0]):
        print('Individual shard IDs cannot be less than 0')
        sys.exit(1)
    if len(args.shard_ids) > args.shard_count:
        print(f'There may be no more than {args.shard_count} shard(s)')
        sys.exit(1)
    m_id = max(args.shard_ids)
    m_val = args.shard_count - 1
    if m_id > m_val:
        print(f'Shard ID {m_id} is invalid. The highest shard ID can be {m_val}')
        sys.exit(1)
print(args)

# Load environment
load_dotenv(dotenv_path=args.env)
if os.getenv('ENABLE_EXPERIMENTS') == '1':
    print('[i] Running with experiments enabled')
if args.cluster_index is not None:
    print('[i] Running in cluster mode')
else:
    print('[i] Running in shard mode')
if 'crowdin-pull' in (args.disable_features or []):
    if not os.path.exists(os.path.join(os.getcwd(), 'i18n_resources')):
        print('[!] The i18n_resources directory does not exist and the crowdin-pull feature is disabled. '
              'This WILL break the bot!')
if args.disable_features:
    os.environ['SC_DISABLED_FEATURES'] = ','.join(args.disable_features)

# Import after loading env
from twitchbot import TwitchBot
bot = TwitchBot.initialize(
    i18n_dir=os.getcwd(),
    shard_count=args.shard_count,
    shard_ids=args.shard_ids)
try:
    bot.run(os.getenv('BOT_TOKEN'), bot=True, reconnect=True)
except KeyboardInterrupt:
    bot.loop.run_until_complete(bot.logout())
