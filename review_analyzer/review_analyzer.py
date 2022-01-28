#!/usr/bin/env python

import pulsar
import argparse
import sys
import json
import os
from dotenv import load_dotenv
import atexit

from ReviewState import ReviewState

from settings import (
    ROLLING_AVERAGE_ALPHA,
)


load_dotenv()


def receiveOrNone(consumer, timeout):
    """
    A modified 'receive' function for a Pulsar topic
    that handles timeouts so that when the topic is empty
    it simply returns None.
    """
    try:
        msg = consumer.receive(timeout)
        return msg
    except Exception as e:
        if 'timeout' in str(e).lower():
            return None
        else:
            raise e


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Analyze restaurant reviews as they come'
    )
    parser.add_argument('-r', '--reviews', help='periodically report reviews', action='store_true', default=False)
    parser.add_argument('-t', '--trolls', help='periodically report troll scores', action='store_true', default=False)
    parser.add_argument('-o', '--outliers', help='report outlier reviews as they come', action='store_true', default=False)
    parser.add_argument('-f', '--frequency', help='frequency of reporting (message count)', type=int, default=200)
    args = parser.parse_args()
    #
    PULSAR_CLIENT_URL = os.environ['PULSAR_CLIENT_URL']
    TOPIC = os.environ['RESTAURANT_TOPIC']
    client = pulsar.Client(PULSAR_CLIENT_URL)
    consumer = client.subscribe(TOPIC,
                                subscription_name='review-analyzer')

    @atexit.register
    def close_pulsar():
        print('Closing Pulsar resources')
        consumer.close()
        client.close()

    # Here we keep state (variables in this process, but may be a Redis or so!)
    reviewState = ReviewState(rollingAlpha=ROLLING_AVERAGE_ALPHA)


    # we basically keep consuming and update our internal state here,
    # handing out updates now and then.
    numReceived = 0
    while True:
        msg = receiveOrNone(consumer, 50)
        if msg:
            numReceived += 1
            msgBody = json.loads(msg.data().decode())

            # let's submit this review to the rolling state
            # (and get notified of whether-outlier as well)
            isOutlier = reviewState.addReview(msgBody)
            #
            if args.outliers and isOutlier:
                print('[%6i] Outlier detected: "%s" on "%s" (%0.2f)' % (
                    numReceived,
                    msgBody['user_id'],
                    msgBody['tgt_name'],
                    msgBody['r_score'],
                ))
            if numReceived % args.frequency == 0:
                if args.reviews:
                    print('[%6i] Restaurant Score Summary:\n                 %s' % (
                        numReceived,
                        ' / '.join(
                            '%s:%0.2f' % (k, v)
                            for k, v in sorted(reviewState.averages().items())
                        )
                    ))
                if args.trolls:
                    print('[%6i] User Trolliness Score:\n                 %s' % (
                        numReceived,
                        ' / '.join(
                            '%s:%0.2f' % (k, v)
                            for k, v in sorted(reviewState.trollinesses().items())
                        )
                    ))
            #


            consumer.acknowledge(msg)
