#!/usr/bin/env python

import json
import itertools
import os
import pulsar
import argparse
from ratelimiter import RateLimiter
from dotenv import load_dotenv

from fake_reviews import createReview, initRandom

load_dotenv()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Generate and publish fake reviews according to a pattern'
    )
    parser.add_argument('-r', '--rate', help='rate per 0.05 seconds', default=10, type=int)
    parser.add_argument('-n', '--number', help='max number of messages', default=None, type=int)
    parser.add_argument('-s', '--seed', help='random seed', default=123, type=int)
    args = parser.parse_args()

    initRandom(args.seed)

    # init connection
    PULSAR_CLIENT_URL = os.environ['PULSAR_CLIENT_URL']
    TENANT = os.environ['TENANT']
    NAMESPACE = os.environ['NAMESPACE']
    RAW_TOPIC = os.environ['RAW_TOPIC']
    client = pulsar.Client(PULSAR_CLIENT_URL)
    streamingTopic = 'persistent://{tenant}/{namespace}/{topic}'.format(
        tenant=TENANT,
        namespace=NAMESPACE,
        topic=RAW_TOPIC,
    )
    producer = client.create_producer(streamingTopic)

    # loop and publish
    rLimiter = RateLimiter(max_calls=args.rate, period=0.05)
    for idx in itertools.count():
        with rLimiter:
            msg = createReview(idx)
            #
            print('* %i ... ' % idx, end ='')
            producer.send(msg.encode('utf-8'))
            print('[%s]' % msg)
        if args.number is not None and idx >= args.number - 1:
            break
