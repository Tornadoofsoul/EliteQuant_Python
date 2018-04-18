#!/usr/bin/env python
# -*- coding: utf-8 -*-
from pandas import Timestamp
import os
import yaml

from source.event.event import EventType
from source.event.backtest_event_engine import BacktestEventEngine
from source.data.backtest_data_feed_quandl import BacktestDataFeedQuandl
from source.data.backtest_data_feed_local import BacktestDataFeedLocal
from source.data.backtest_data_feed_tushare import BacktestDataFeedTushare
from source.data.data_board import DataBoard
from source.brokerage.backtest_brokerage import BacktestBrokerage
from source.position.portfolio_manager import PortfolioManager
from source.performance.performance_manager import PerformanceManager
from source.risk.risk_manager import PassThroughRiskManager
from source.strategy.mystrategy import strategy_list

class Backtest(object):
    """
    Event driven backtest engine
    """
    def __init__(self, config):
        """
        1. read in configs
        2. Set up backtest event engine
        """
        self._current_time = Timestamp('1900-01-01')

        ## 0. read in configs
        self._initial_cash = config['cash']
        self._symbols = config['tickers']
        self._benchmark = config['benchmark']
        #self.start_date = datetime.datetime.strptime(config['start_date'], "%Y-%m-%d")
        #self.end_date = datetime.datetime.strptime(config['end_date'], "%Y-%m-%d")
        start_date = config['start_date']
        send_date = config['end_date']
        strategy_name = config['strategy']
        datasource = str(config['datasource'])
        self._hist_dir = config['hist_dir']
        self._output_dir = config['output_dir']

        ## 1. data_feed
        symbols_all = self._symbols[:]   # copy
        if self._benchmark is not None:
            symbols_all.append(self._benchmark)
        self._symbols = [str(s) for s in self._symbols]
        symbols_all = [str(s) for s in symbols_all]

        if (datasource.upper() == 'LOCAL'):
            self._data_feed = BacktestDataFeedLocal(
                hist_dir=self._hist_dir,
                start_date=start_date, end_date=send_date
            )
        elif (datasource.upper() == 'TUSHARE'):
            self._data_feed = BacktestDataFeedTushare(
                start_date=start_date, end_date=send_date
            )
        else:
            self._data_feed = BacktestDataFeedQuandl(
                start_date=start_date, end_date=send_date
            )

        self._data_feed.subscribe_market_data(symbols_all)

        ## 2. event engine
        self._events_engine = BacktestEventEngine(self._data_feed)

        ## 3. brokerage
        self._data_board = DataBoard()
        self._backtest_brokerage = BacktestBrokerage(
            self._events_engine, self._data_board
        )

        ## 4. portfolio_manager
        self._portfolio_manager = PortfolioManager(self._initial_cash)

        ## 5. performance_manager
        self._performance_manager = PerformanceManager(symbols_all)

        ## 6. risk_manager
        self._risk_manager = PassThroughRiskManager()

        ## 7. load all strategies
        strategyClass = strategy_list.get(strategy_name, None)
        if not strategyClass:
            print(u'can not find strategy：%s' % strategy_name)
            return
        self._strategy = strategyClass(self._events_engine)
        self._strategy.on_init()
        self._strategy.on_start()

        ## 8. trade recorder
        #self._trade_recorder = ExampleTradeRecorder(output_dir)

        ## 9. wire up event handlers
        self._events_engine.register_handler(EventType.TICK, self._tick_event_handler)
        self._events_engine.register_handler(EventType.BAR, self._bar_event_handler)
        self._events_engine.register_handler(EventType.ORDER, self._order_event_handler)
        self._events_engine.register_handler(EventType.FILL, self._fill_event_handler)

    # ------------------------------------ private functions -----------------------------#
    def _tick_event_handler(self, tick_event):
        self._current_time = tick_event.timestamp

        # performance update goes before position updates because it updates previous day performance
        self._performance_manager.update_performance(self._current_time, self._portfolio_manager, self._data_board)
        self._portfolio_manager.mark_to_market(self._current_time, tick_event.full_symbol, tick_event.price)
        self._data_board.on_tick(tick_event)
        self._strategy.on_tick(tick_event)

    def _bar_event_handler(self, bar_event):
        self._current_time = bar_event.bar_end_time()

        # performance update goes before position updates because it updates previous day
        self._performance_manager.update_performance(self._current_time, self._portfolio_manager, self._data_board)
        self._portfolio_manager.mark_to_market(self._current_time, bar_event.full_symbol, bar_event.adj_close_price)
        self._data_board.on_bar(bar_event)
        self._strategy.on_bar(bar_event)

    def _order_event_handler(self, order_event):
        self._backtest_brokerage.place_order(order_event)

    def _fill_event_handler(self, fill_event):
        self._portfolio_manager.on_fill(fill_event)
        self._performance_manager.on_fill(fill_event)

    # -------------------------------- end of private functions -----------------------------#

    # -------------------------------------- public functions -------------------------------#
    def run(self):
        """
        Run backtest
        """
        self._events_engine.run()
        self._performance_manager.update_final_performance(self._current_time, self._portfolio_manager, self._data_board)
        self._performance_manager.save_results(self._output_dir)
        self._performance_manager.create_tearsheet()

    # ------------------------------- end of public functions -----------------------------#

if __name__ == '__main__':
    config = None
    try:
        path = os.path.abspath(os.path.dirname(__file__))
        config_file = os.path.join(path, 'config_backtest.yaml')
        with open(os.path.expanduser(config_file)) as fd:
            config = yaml.load(fd)
    except IOError:
        print("config.yaml is missing")

    backtest = Backtest(config)
    results = backtest.run()