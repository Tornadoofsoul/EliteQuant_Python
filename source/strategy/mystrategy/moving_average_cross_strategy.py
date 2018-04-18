#!/usr/bin/env python
# -*- coding: utf-8 -*-
from collections import deque
import numpy as np

from ..strategy_base import StrategyBase
from ...order.order_event import OrderEvent
from ...order.order_type import OrderType


class MovingAverageCrossStrategy(StrategyBase):
    """
	classical MovingAverageCrossStrategy, golden cross
    """

    def __init__(
            self, events_engine,
            short_window=50, long_window=200
    ):
        super(MovingAverageCrossStrategy, self).__init__(events_engine)
        self.short_window = short_window
        self.long_window = long_window
        self.bars = 0
        self.invested = False
        self.prices = []
        self.symbols = ['AAPL']

    def on_bar(self, bar_event):
        symbol = self.symbols[0]
        # Only applies SMA to first ticker
        if symbol != bar_event.full_symbol:
            return
        # Add latest adjusted closing price to price list
        self.prices.append(bar_event.adj_close_price)
        self.bars += 1

        # wait for enough bars
        if self.bars >= self.long_window:
            # Calculate the simple moving averages
            short_sma = np.mean(self.prices[-self.short_window:])
            long_sma = np.mean(self.prices[-self.long_window:])
            # Trading signals based on moving average cross
            if short_sma > long_sma and not self.invested:
                print("Long: %s, short_sma %s, long_sma %s" % ( bar_event.bar_end_time(), str(short_sma), str(long_sma) ))
                o = OrderEvent()
                o.full_symbol = symbol
                o.order_type = OrderType.MARKET
                o.order_size = 100
                self.place_order(o)
                self.invested = True
            elif short_sma < long_sma and self.invested:
                print("Short: %s, short_sma %s, long_sma %s" % (bar_event.bar_end_time(), str(short_sma), str(long_sma)))
                o = OrderEvent()
                o.full_symbol = symbol
                o.order_type = OrderType.MARKET
                o.order_size = -100
                self.place_order(o)
                self.invested = False
