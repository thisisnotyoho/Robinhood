"""Robinhood.py: a collection of utilities for working with Robinhood's Private API"""
import getpass
import logging
import warnings
from enum import Enum

import requests
import six
from six.moves.urllib.parse import unquote
from six.moves.urllib.request import getproxies
from six.moves import input
from . import exceptions as RH_exception

class Bounds(Enum):
    """enum for bounds in `historicals` endpoint"""
    REGULAR = 'regular'
    EXTENDED = 'extended'


class Transaction(Enum):
    """enum for buy/sell orders"""
    BUY = 'buy'
    SELL = 'sell'


class Robinhood:
    """wrapper class for fetching/parsing Robinhood endpoints"""
    endpoints = {
        "login": "https://api.robinhood.com/api-token-auth/",
        "logout": "https://api.robinhood.com/api-token-logout/",
        "investment_profile": "https://api.robinhood.com/user/investment_profile/",
        "accounts": "https://api.robinhood.com/accounts/",
        "ach_iav_auth": "https://api.robinhood.com/ach/iav/auth/",
        "ach_relationships": "https://api.robinhood.com/ach/relationships/",
        "ach_transfers": "https://api.robinhood.com/ach/transfers/",
        "applications": "https://api.robinhood.com/applications/",
        "cards": "https://api.robinhood.com/midlands/notifications/stack/",
        "dividends": "https://api.robinhood.com/dividends/",
        "edocuments": "https://api.robinhood.com/documents/",
        "instruments": "https://api.robinhood.com/instruments/",
        "margin_upgrades": "https://api.robinhood.com/margin/upgrades/",
        "markets": "https://api.robinhood.com/markets/",
        "notifications": "https://api.robinhood.com/notifications/",
        "orders": "https://api.robinhood.com/orders/",
        "password_reset": "https://api.robinhood.com/password_reset/request/",
        "portfolios": "https://api.robinhood.com/portfolios/",
        "positions": "https://api.robinhood.com/positions/",
        "quotes": "https://api.robinhood.com/quotes/",
        "historicals": "https://api.robinhood.com/quotes/historicals/",
        "document_requests": "https://api.robinhood.com/upload/document_requests/",
        "user": "https://api.robinhood.com/user/",
        "watchlists": "https://api.robinhood.com/watchlists/",
        "news": "https://api.robinhood.com/midlands/news/",
        "fundamentals": "https://api.robinhood.com/fundamentals/",
    }

    session = None

    username = None

    password = None

    headers = None

    auth_token = None

    logger = logging.getLogger('Robinhood')
    logger.addHandler(logging.NullHandler())

    ##############################
    #Logging in and initializing
    ##############################

    def __init__(self):
        self.session = requests.session()
        self.session.proxies = getproxies()
        self.headers = {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "en;q=1, fr;q=0.9, de;q=0.8, ja;q=0.7, nl;q=0.6, it;q=0.5",
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
            "X-Robinhood-API-Version": "1.0.0",
            "Connection": "keep-alive",
            "User-Agent": "Robinhood/823 (iPhone; iOS 7.1.2; Scale/2.00)"
        }
        self.session.headers = self.headers

    def login_prompt(self): #pragma: no cover
        """Prompts user for username and password and calls login()."""
        username = input("Username: ")
        password = getpass.getpass()
        return self.login(username=username, password=password)

    def login(
            self,
            username,
            password,
            mfa_code=None
        ):
        """save and test login info for Robinhood accounts

        Args:
            username (str): username
            password (str): password

        Returns:
            (bool): received valid auth token

        """
        self.username = username
        self.password = password
        payload = {
            'password': self.password,
            'username': self.username
        }

        if mfa_code:
            payload['mfa_code'] = mfa_code

        try:
            res = self.session.post(
                self.endpoints['login'],
                data=payload
            )
            res.raise_for_status()
            data = res.json()
        except requests.exceptions.HTTPError:
            raise RH_Exception.LoginFailed()

        if 'mfa_required' in data.keys():           #pragma: no cover
            raise RH_Exception.TwoFactorRequired()  #requires a second call to enable 2FA

        if 'token' in data.keys():
            self.set_token(data['token'])
            return True

        return False

    def set_token(self,token):
        self.auth_token = token
        self.headers['Authorization'] = 'Token ' + self.auth_token

    def logout(self):
        """logout from Robinhood

        Returns:
            (:obj:`requests.request`) result from logout endpoint

        """
        try:
            req = self.session.post(self.endpoints['logout'])
            req.raise_for_status()
        except requests.exceptions.HTTPError as err_msg:
            warnings.warn('Failed to log out ' + repr(err_msg))

        self.headers['Authorization'] = None
        self.auth_token = None

        return req

    ##############################
    #GET DATA
    ##############################

    def investment_profile(self):
        """fetch investment_profile"""
        res = self.session.get(self.endpoints['investment_profile'])
        res.raise_for_status()  #will throw without auth
        data = res.json()
        return data

    def instruments(self, stock):
        """fetch instruments endpoint

        Args:
            stock (str): stock ticker

        Returns:
            (:obj:`dict`): JSON contents from `instruments` endpoint

        """
        res = self.session.get(
            self.endpoints['instruments'],
            params={'query': stock.upper()}
        )
        res.raise_for_status()
        res = res.json()

        # if requesting all, return entire object so may paginate with ['next']
        if (stock == ""):
            return res

        return res['results']

    def quote_data(self, stock=''):
        """fetch stock quote

        Args:
            stock (str): stock ticker, prompt if blank

        Returns:
            (:obj:`dict`): JSON contents from `quotes` endpoint

        """
        url = None
        if stock.find(',') == -1:
            url = str(self.endpoints['quotes']) + str(stock) + "/"
        else:
            url = str(self.endpoints['quotes']) + "?symbols=" + str(stock)
        #Check for validity of symbol
        try:
            req = requests.get(url)
            req.raise_for_status()
            data = req.json()
        except requests.exceptions.HTTPError:
            raise NameError('Invalid Symbol: ' + stock) #TODO: custom exception

        return data

    # We will keep for compatibility until next major release
    def quotes_data(self, stocks):
        """Fetch quote for multiple stocks, in one single Robinhood API call

        Args:
            stocks (list<str>): stock tickers

        Returns:
            (:obj:`list` of :obj:`dict`): List of JSON contents from `quotes` endpoint, in the
            same order of input args. If any ticker is invalid, a None will occur at that position.
        """
        url = str(self.endpoints['quotes']) + "?symbols=" + ",".join(stocks)
        try:
            req = requests.get(url)
            req.raise_for_status()
            data = req.json()
        except requests.exceptions.HTTPError:
            raise NameError('Invalid Symbols: ' + ",".join(stocks)) #TODO: custom exception

        return data["results"]

    def get_quote_list(self, stock='', key=''):
        """Returns multiple stock info and keys from quote_data (prompt if blank)

        Args:
            stock (str): stock ticker (or tickers separated by a comma)
            , prompt if blank
            key (str): key attributes that the function should return

        Returns:
            (:obj:`list`): Returns values from each stock or empty list
                           if none of the stocks were valid

        """
        #Creates a tuple containing the information we want to retrieve
        def append_stock(stock):
            keys = key.split(',')
            myStr = ''
            for item in keys:
                myStr += stock[item] + ","
            return (myStr.split(','))
        #Prompt for stock if not entered
        if not stock:   #pragma: no cover
            stock = input("Symbol: ")
        data = self.quote_data(stock)
        res = []
        # Handles the case of multple tickers
        if stock.find(',') != -1:
            for stock in data['results']:
                if stock == None:
                    continue
                res.append(append_stock(stock))
        else:
            res.append(append_stock(data))
        return res

    def get_quote(self, stock=''):
        """wrapper for quote_data"""
        data = self.quote_data(stock)
        return data

    def get_historical(
            self,
            stock,
            interval,
            span,
            bounds=Bounds.REGULAR
        ):
        """fetch historical data for stock

        Note: valid interval/span configs
            interval = 5minute | 10minute + span = day, week
            interval = day + span = year
            interval = week
            TODO: NEEDS TESTS

        Args:
            stock (str): stock ticker
            interval (str): resolution of data
            span (str): length of data
            bounds (:enum:`Bounds`, optional): 'extended' or 'regular' trading hours

        Returns:
            (:obj:`dict`) values returned from `historicals` endpoint

        """
        if isinstance(bounds, str): #recast to Enum
            bounds = Bounds(bounds)

        params = {
            'interval': interval,
            'span': span,
            'bounds': bounds.name.lower()
        }
        endpoint = self.endpoints['historicals'] + stock.upper() + '/'
        res = self.session.get(
            endpoint,
            params=params
        )
        return res.json()

    def get_historical_quotes(
            self,
            stocks,
            interval,
            span,
            bounds=Bounds.REGULAR
        ):
        """fetch historical data for stock

        Note: valid interval/span configs
            interval = 5minute | 10minute + span = day, week
            interval = day + span = year
            interval = week
            TODO: NEEDS TESTS

        Args:
            stocks (list): stock tickers
            interval (str): resolution of data
            span (str): length of data
            bounds (:enum:`Bounds`, optional): 'extended' or 'regular' trading hours

        Returns:
            (:obj:`dict`) values returned from `historicals` endpoint

        """
        if len(stocks) > 75:
            chunks = [stocks[i:i+75] for i in range(0,len(stocks),75)]
            ret = []
            for chunk in chunks:
                ret += self.get_historical_quotes(chunk,interval,span,bounds)
            return ret

        if isinstance(bounds, str): #recast to Enum
            bounds = Bounds(bounds)


        params = {
            'symbols' : ",".join(stocks),
            'interval': interval,
            'span': span,
            'bounds': bounds.name.lower()
        }
        res = self.session.get(
            self.endpoints['historicals'],
            params=params
        )
        return res.json()['results']

    def get_news(self, stock):
        """fetch news endpoint
        Args:
            stock (str): stock ticker

        Returns:
            (:obj:`dict`) values returned from `news` endpoint

        """
        return self.session.get(self.endpoints['news']+stock.upper()+"/").json()

    def print_quote(self, stock=''):    #pragma: no cover
        """print quote information
        Args:
            stock (str): ticker to fetch

        Returns:
            None

        """
        data = self.get_quote_list(stock,'symbol,last_trade_price')
        for item in data:
            quote_str = item[0] + ": $" + item[1]
            print(quote_str)
            self.logger.info(quote_str)

    def print_quotes(self, stocks): #pragma: no cover
        """print a collection of stocks

        Args:
            stocks (:obj:`list`): list of stocks to pirnt

        Returns:
            None

        """
        for stock in stocks:
            self.print_quote(stock)

    def ask_price(self, stock=''):
        """get asking price for a stock

        Note:
            queries `quote` endpoint, dict wrapper

        Args:
            stock (str): stock ticker

        Returns:
            (float): ask price

        """
        return self.get_quote_list(stock,'ask_price')

    def ask_size(self, stock=''):
        """get ask size for a stock

        Note:
            queries `quote` endpoint, dict wrapper

        Args:
            stock (str): stock ticker

        Returns:
            (int): ask size

        """
        return self.get_quote_list(stock,'ask_size')

    def bid_price(self, stock=''):
        """get bid price for a stock

        Note:
            queries `quote` endpoint, dict wrapper

        Args:
            stock (str): stock ticker

        Returns:
            (float): bid price

        """
        return self.get_quote_list(stock,'bid_price')

    def bid_size(self, stock=''):
        """get bid size for a stock

        Note:
            queries `quote` endpoint, dict wrapper

        Args:
            stock (str): stock ticker

        Returns:
            (int): bid size

        """
        return self.get_quote_list(stock,'bid_size')

    def last_trade_price(self, stock=''):
        """get last trade price for a stock

        Note:
            queries `quote` endpoint, dict wrapper

        Args:
            stock (str): stock ticker

        Returns:
            (float): last trade price

        """
        return self.get_quote_list(stock,'last_trade_price')

    def previous_close(self, stock=''):
        """get previous closing price for a stock

        Note:
            queries `quote` endpoint, dict wrapper

        Args:
            stock (str): stock ticker

        Returns:
            (float): previous closing price

        """
        return self.get_quote_list(stock,'previous_close')

    def previous_close_date(self, stock=''):
        """get previous closing date for a stock

        Note:
            queries `quote` endpoint, dict wrapper

        Args:
            stock (str): stock ticker

        Returns:
            (str): previous close date

        """
        return self.get_quote_list(stock,'previous_close_date')

    def adjusted_previous_close(self, stock=''):
        """get adjusted previous closing price for a stock

        Note:
            queries `quote` endpoint, dict wrapper

        Args:
            stock (str): stock ticker

        Returns:
            (float): adjusted previous closing price

        """
        return self.get_quote_list(stock,'adjusted_previous_close')

    def symbol(self, stock=''):
        """get symbol for a stock

        Note:
            queries `quote` endpoint, dict wrapper

        Args:
            stock (str): stock ticker

        Returns:
            (str): stock symbol

        """
        return self.get_quote_list(stock,'symbol')

    def last_updated_at(self, stock=''):
        """get last update datetime

        Note:
            queries `quote` endpoint, dict wrapper

        Args:
            stock (str): stock ticker

        Returns:
            (str): last update datetime

        """
        return self.get_quote_list(stock,'last_updated_at')
        #TODO: recast to datetime object?

    def get_account(self):
        """fetch account information

        Returns:
            (:obj:`dict`): `accounts` endpoint payload

        """
        res = self.session.get(self.endpoints['accounts'])
        res.raise_for_status()  #auth required
        res = res.json()
        return res['results'][0]

    def get_url(self, url):
        """flat wrapper for fetching URL directly"""
        return self.session.get(url).json()

    ##############################
    #GET FUNDAMENTALS
    ##############################

    def get_fundamentals(self, stock=''):
        """find stock fundamentals data

        Args:
            (str): stock ticker

        Returns:
            (:obj:`dict`): contents of `fundamentals` endpoint

        """
        #Prompt for stock if not entered
        if not stock:   #pragma: no cover
            stock = input("Symbol: ")

        url = str(self.endpoints['fundamentals']) + str(stock.upper()) + "/"
        #Check for validity of symbol
        try:
            req = requests.get(url)
            req.raise_for_status()
            data = req.json()
        except requests.exceptions.HTTPError:
            raise NameError('Invalid Symbol: ' + stock) #TODO wrap custom exception

        return data


    def fundamentals(self, stock=''):
        """wrapper for get_fundamentlals function"""
        return self.get_fundamentals(stock)

    ##############################
    # PORTFOLIOS DATA
    ##############################

    def portfolios(self):
        """Returns the user's portfolio data."""
        req = self.session.get(self.endpoints['portfolios'])
        req.raise_for_status()
        return req.json()['results'][0]

    def adjusted_equity_previous_close(self):
        """wrapper for portfolios

        get `adjusted_equity_previous_close` value

        """
        return float(self.portfolios()['adjusted_equity_previous_close'])

    def equity(self):
        """wrapper for portfolios

        get `equity` value

        """
        return float(self.portfolios()['equity'])

    def equity_previous_close(self):
        """wrapper for portfolios

        get `equity_previous_close` value

        """
        return float(self.portfolios()['equity_previous_close'])

    def excess_margin(self):
        """wrapper for portfolios

        get `excess_margin` value

        """
        return float(self.portfolios()['excess_margin'])

    def extended_hours_equity(self):
        """wrapper for portfolios

        get `extended_hours_equity` value

        """
        try:
            return float(self.portfolios()['extended_hours_equity'])
        except TypeError:
            return None

    def extended_hours_market_value(self):
        """wrapper for portfolios

        get `extended_hours_market_value` value

        """
        try:
            return float(self.portfolios()['extended_hours_market_value'])
        except TypeError:
            return None

    def last_core_equity(self):
        """wrapper for portfolios

        get `last_core_equity` value

        """
        return float(self.portfolios()['last_core_equity'])

    def last_core_market_value(self):
        """wrapper for portfolios

        get `last_core_market_value` value

        """
        return float(self.portfolios()['last_core_market_value'])

    def market_value(self):
        """wrapper for portfolios

        get `market_value` value

        """
        return float(self.portfolios()['market_value'])

    def order_history(self):
        """wrapper for portfolios

        get orders from account

        """
        return self.session.get(self.endpoints['orders']).json()

    def dividends(self):
        """wrapper for portfolios

        get dividends from account

        """
        return self.session.get(self.endpoints['dividends']).json()

    ##############################
    # WATCHLIST DATA
    ##############################
    def get_watchlists(self):
        """Returns names of user-defined watchlists"""
        return self.session.get(self.endpoints['watchlists']).json()

    def create_watchlist(self,
                         name,
        ):
        """Creates a watchlist

        Args:
            name (string): the name of the watchlist to create

        Returns:
            (:obj:`dict`): `watchlists` endpoint payload
        """
        payload = { 'name' : name }
        return self.session.post(self.endpoints['watchlists'],
                                 data=payload).json()

    def watchlist_bulk_add(self,
                           watchlist_name,
                           symbols
        ):
        """Adds symbols to a watchlist

        Args:
            watchlist_name (string): the name of the watchlist to bulk_add to
            symbols (list): Symbols to add to the watchlist (max 32)

        Returns:
            (:obj:`dict`): `watchlists` endpoint payload
        """
        payload = {'symbols' : ",".join(symbols).upper()}
        endpoint = self.endpoints['watchlists']+watchlist_name+'/bulk_add/'
        return self.session.post(endpoint,
                                 data=payload).json()

    def watchlist_remove_item(self,
                              watchlist_name,
                              symbol
        ):
        """Removes a symbol from a watchlist

        Args:
            watchlist_name (string): the name of the watchlist to remove from
            symbol (list): The symbol to remove from the watchlist

        Returns:
            (:obj:`dict`): `watchlists` endpoint payload
        """
        instrument_id = self.instruments(symbol)['id']
        endpoint = self.endpoints['watchlists']+watchlist_name+'/'+instrument_id
        return self.session.delete(endpoint).json()

    def delete_watchlist(self,
                         watchlist_name
        ):
        """Deletes a watchlist
            NOTE: this isn't in the robinhood API ***EXPERIMENTAL***

        Args:
            watchlist_name (string): the name of the watchlist to delete

        Returns:
            (:obj:`dict`): `watchlists` endpoint payload
        """
        endpoint = self.endpoints['watchlists']+watchlist_name+'/'
        return self.session.delete(endpoint).json()

    def get_watchlist_instruments(self,
                                  watchlist_name):
        """Gets the instruments in a watchlist

        Args:
            watchlist_name (string): the name of the watchlist to retrieve

        Returns:
            (:obj:`dict`): `watchlists` endpoint payload
        """
        endpoint = self.endpoints['watchlists']+watchlist_name+'/'
        return self.session.get(endpoint).json()

    ##############################
    # CARDS
    ##############################
    def get_cards(self):
        return self.session.get(self.endpoints['cards']).json()['results']

    def dismiss_card(self, card_id):
        endpoint = self.endpoints['cards']+card_id+'/dismiss/'
        return self.session.post(endpoint).json()

    ##############################
    # POSITIONS DATA
    ##############################

    def positions(self):
        """Returns the user's positions data."""
        return self.session.get(self.endpoints['positions']).json()

    def securities_owned(self):
        """
        Returns a list of symbols of securities of which there are more
        than zero shares in user's portfolio.
        """
        return self.session.get(self.endpoints['positions']+'?nonzero=true').json()

    ##############################
    #PLACE ORDER
    ##############################

    def place_order(
            self,
            instrument,
            quantity,
            transaction,
            bid_price=None,
            stop_price=None,
            trigger='immediate',
            order='market',
            time_in_force = 'gfd',
        ):
        """place an order with Robinhood

        Notes:
            OMFG TEST THIS PLEASE!

        Args:
            instrument (dict): the RH URL and symbol in dict for the instrument to be traded
            quantity (int): quantity of stocks in order
            bid_price (float): price for order
            transaction (:enum:`Transaction`): BUY or SELL enum
            trigger (:enum:`Trigger`): IMMEDIATE or STOP enum
            order (:enum:`Order`): MARKET or LIMIT
            time_in_force (:enum:`TIME_IN_FORCE`): GFD or GTC (day or until cancelled)

        Returns:
            (:obj:`requests.request`): result from `orders` put command

        """
        if isinstance(transaction, str):
            transaction = Transaction(transaction)

        payload = {
            'account': self.get_account()['url'],
            'instrument': unquote(instrument['url']),
            'quantity': quantity,
            'side': transaction.name.lower(),
            'symbol': instrument['symbol'],
            'time_in_force': time_in_force.lower(),
            'trigger': trigger,
            'type': order.lower()
        }
        if trigger == 'stop':
            payload['stop_price'] = float(stop_price)
        if order == 'limit':
            payload['price'] = float(bid_price)

        if (trigger == 'immediate' and
            order == 'market' and
            transaction.name.lower() == 'buy'):
            # A note here, this is what the App does for market buys.
            # see https://support.robinhood.com/hc/en-us/articles/208650386-Order-Types
            # and https://github.com/sanko/Robinhood/issues/11
            payload['price'] = self.quote_data(instrument['symbol'])['bid_price']*1.05
             
        res = self.session.post(
            self.endpoints['orders'],
            data=payload
        )
        res.raise_for_status()
        return res


    ##############################
    #GET OPEN ORDER(S)
    ##############################
    
    def get_open_orders(self):
        """
        Returns all currently open (cancellable) orders.
        If not orders are currently open, `None` is returned.
        TODO: Is there a way to get these from the API endpoint without stepping through order history?
        """

        open_orders = []
        orders = self.order_history()
        for order in orders['results']:
            if(order['cancel'] is not None): 
                open_orders.append(order)
                print(type(order))

        if len(open_orders) > 0:
            return open_orders

    ##############################
    #CANCEL ORDER(S)
    ##############################

    def cancel_order(
            self,
            order_id
    ): 
        """
        Cancels specified order and returns the response (results from `orders` command). 
        If order cannot be cancelled, `None` is returned.

        Args:
            order_id (str): Order ID that is to be cancelled or order dict returned from
            order get.

        """
        if order_id is str:
            try:
                order = self.session.get(self.endpoints['orders'] + order_id).json()
            except (requests.exceptions.HTTPError)  as err_msg:
                raise ValueError('Invalid order id: ' + order_id)
       
        if order.get('cancel') is not None:
            try: 
                req = self.session.post(order['cancel'])
                req.raise_for_status()
                #TODO: confirm that the order has been dropped 

            except (requests.exceptions.HTTPError)  as err_msg:
                raise ValueError('Failed to cancel order ID: ' + order_id
                     + '\n Error message: '+ repr(err_msg))
                return None
            
        # no cancel link - order type cannot be cancelled
        else: 
            raise ValueError('No cancel link - unable to cancel order ID: '+ order_id)

        return order

    def cancel_open_orders(self):
        """
        Cancels all open orders and returns the responses from the canelled orders (results from `orders` command). 
        If no orders are open or no orders were cancelled (i.e. failed to cancel), returns `None`
        """
        cancelled_orders = []
        open_orders = self.get_open_orders()

        # no open orders 
        if open_orders is None: 
            return None

        for order in open_orders:
            cancel_order(order['id'])
            cancelled_orders.append(order)
        
        return cancelled_orders
