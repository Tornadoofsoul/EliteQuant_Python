#!/usr/bin/env python
# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import pyfolio as pf

class PerformanceManager(object):
    """
    Record equity, positions, and trades in accordance to pyfolio format
    First date will be the first data start date
    """
    def __init__(self, symbols):
        self._symbols = symbols
        self._slippage = 0.0
        self._commission_rate = 0.0
        self.reset()

    # ------------------------------------ public functions -----------------------------#
    #  or each sid
    def reset(self):
        self._realized_pnl = 0.0
        self._unrealized_pnl = 0.0

        self._equity = pd.Series()      # equity line
        self._df_positions = pd.DataFrame(columns=self._symbols+['cash'])
        self._df_trades = pd.DataFrame(columns=['amount', 'price', 'symbol'])

    def set_splippage(self, slippage):
        self._slippage = slippage

    def set_commission_rate(self, commission_rate):
        self._commission_rate = commission_rate

    def update_performance(self, current_time, position_manager, data_board):
        if self._equity.empty:
            self._equity[current_time] = 0.0
            return
        # on a new time/date, calculate the performances for the last date
        elif current_time != self._equity.index[-1]:
            performance_time = self._equity.index[-1]

            equity = 0.0
            self._df_positions.loc[performance_time] = [0] * (len(self._symbols) + 1)
            for sym, pos in position_manager.positions.items():
                equity += pos.size * data_board.get_last_price(sym)
                self._df_positions.loc[performance_time, sym] = pos.size * data_board.get_last_price(sym)
            self._df_positions.loc[performance_time, 'cash'] = position_manager.cash

            self._equity[performance_time] = equity + position_manager.cash

            self._equity[current_time] = 0.0

    def on_fill(self, fill_event):
        # self._df_trades.loc[fill_event.timestamp] = [fill_event.fill_size, fill_event.fill_price, fill_event.full_symbol]
        self._df_trades = self._df_trades.append(pd.DataFrame(
            {'amount': [fill_event.fill_size], 'price': [fill_event.fill_price], 'symbol': [fill_event.full_symbol]},
            index=[fill_event.fill_time]))

    def update_final_performance(self, current_time, position_manager, data_board):
        """
        When a new data date comes in, it calcuates performances for the previous day
        This leaves the last date not updated.
        So we call the update explicitly
        """
        performance_time = current_time

        equity = 0.0
        self._df_positions.loc[performance_time] = [0] * (len(self._symbols) + 1)
        for sym, pos in position_manager.positions.items():
            equity += pos.size * data_board.get_last_price(sym)
            self._df_positions.loc[performance_time, sym] = pos.size * data_board.get_last_price(sym)
        self._df_positions.loc[performance_time, 'cash'] = position_manager.cash

        self._equity[performance_time] = equity + position_manager.cash

    def create_tearsheet(self):
        rets = self._equity.pct_change()
        rets = rets[1:]
        rets.index = rets.index.tz_localize('UTC')
        self._df_positions.index = self._df_positions.index.tz_localize('UTC')
        self._df_trades.index = self._df_trades.index.tz_localize('UTC')
        #pf.create_full_tear_sheet(rets, self._df_positions, self._df_trades)
        pf.create_simple_tear_sheet(rets,benchmark_rets=rets)

    def save_results(self, output_dir):
        self._equity.to_csv(output_dir + '/equity.csv')
        self._df_positions.to_csv(output_dir + '/positions.csv')
        self._df_trades.to_csv(output_dir + '/trades.csv')
    # ------------------------------- end of public functions -----------------------------#