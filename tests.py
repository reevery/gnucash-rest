import unittest
import json
import gnucash
import gnucash_rest
import MySQLdb
import warnings
import sys

class ApiTestCase(unittest.TestCase):

    def setUp(self):
        self.app = gnucash_rest.app.test_client()
        self.app.testing = True

    def setup_database(self):
        database = MySQLdb.connect(host='localhost', user='root', passwd='oxford')
        cursor = database.cursor()
        sql = 'CREATE DATABASE test'
        cursor.execute(sql)

    def teardown_database(self):
        warnings.filterwarnings('ignore', category = MySQLdb.Warning)
        database = MySQLdb.connect(host='localhost', user='root', passwd='oxford')
        cursor = database.cursor()
        sql = 'DROP DATABASE IF EXISTS test'
        cursor.execute(sql)

    # probably not the most pythonic way to do this
    def clean(self, data):
        # convert bytes to Python 3 string if required
        if sys.version_info >= (3,0):
            return data.decode("utf-8")
        else:
            return data

    def get_error_type(self, method, url, data):
        if method is 'get':
            response = self.app.get(url)
        elif method is 'post':
            response = self.app.post(url, data=data)
        elif method is 'delete':
            response = self.app.delete(url, data=data)
        else:
            raise ValueError('unknown method in assert_error_type')

        if response.status == '400 BAD REQUEST':
            json_response = json.loads(self.clean(response.data))
            return json_response['errors'][0]['type']
        else:
            raise ValueError('Non 400 error code: ' + response.status)

    def createVendor(self):

        data = dict(
            id = '999999',
            name = 'Test vendor',
            address_line_1 = 'Test address',
            currency = 'GBP'
        )

        return json.loads(self.clean(self.app.post('/vendors', data=data).data))

    def createCustomer(self):

        data = dict(
            id = '999999',
            name = 'Test customer',
            address_line_1 = 'Test address',
            currency = 'GBP'
        )

        return json.loads(self.clean(self.app.post('/customers', data=data).data))

    def createInvoice(self):

        data = dict(
            id = '999999',
            customer_id = self.createCustomer()['id'],
            date_opened = '2010-01-01',
            currency = 'GBP'
        )

        return json.loads(self.clean(self.app.post('/invoices', data=data).data))

    def createAccount(self):

        data = dict(
            name = 'Test',
            currency  = 'GBP',
            account_type_id = '2'
        )

        return json.loads(self.clean(self.app.post('/accounts', data=data).data))

class ApiSessionTestCase(ApiTestCase):

    def setUp(self):
        self.app = gnucash_rest.app.test_client()
        self.app.testing = True

        # remove the database in case tests failed previously
        self.teardown_database()

        self.setup_database()

        data = dict(
            connection_string = 'mysql://root:oxford@localhost/test',
            is_new = '1',
            ignore_lock = '0'
        )

        response = self.app.post('/session', data=data)
        assert self.clean(response.data) == '"Session started"'

    def tearDown(self):

        response = self.app.delete('/session')
        assert self.clean(response.data) == '"Session ended"'

        self.teardown_database()

class RootTestCase(ApiTestCase):

    def test_root(self):
        response = self.app.get('/')
        assert self.clean(response.data) == '"Gnucash REST API"'

    def test_root_cors(self):
        gnucash_rest.app.cors_origin = '*'

        response = self.app.get('/')
        assert response.headers['Access-Control-Allow-Origin'] == '*'

        del gnucash_rest.app.cors_origin

class SessionTestCase(ApiTestCase):

    def test_no_session(self):
        data = dict()
        assert self.get_error_type('get', '/accounts', data) == 'SessionDoesNotExist'

    def test_session_no_params(self):
        data = dict()
        assert self.get_error_type('post', '/session', data) == 'InvalidConnectionString'

    def test_session_connection_string(self):
        data = dict(
            connection_string = 'mysql://root:oxford@localhost/test'
        )
        assert self.get_error_type('post', '/session', data) == 'InvalidIsNew'

    def test_session_isnew(self):
        data = dict(
            connection_string = 'mysql://root:oxford@localhost/test',
            is_new='1'
        )
        assert self.get_error_type('post', '/session', data) == 'InvalidIgnoreLock'

    def test_session_auto_error(self):
        gnucash_rest.app.connection_string = 'mysql://root:oxford@localhost/none'

        # remove the database in case tests failed previously
        self.teardown_database()

        self.setup_database()

        # Logs
        # CRIT <gnc.backend.dbi> [GncDbiBackend<Type>::session_begin()] Database 'none' does not exist

        error = gnucash_rest.startup()
        assert error.data['code'] == 'ERR_BACKEND_NO_SUCH_DB'

        self.teardown_database()

        del gnucash_rest.app.connection_string

    def test_session_auto(self):
        gnucash_rest.app.connection_string = 'mysql://root:oxford@localhost/test'

        # remove the database in case tests failed previously
        self.teardown_database()

        self.setup_database()

        database = gnucash_rest.startup()
        assert isinstance(database, gnucash.gnucash_core.Session)

        # Logs
        # CRIT <gnc.backend.dbi> gnc_dbi_unlock: assertion 'dbi_conn_error( dcon, NULL ) == 0' failed

        response = self.app.delete('/session')
        assert self.clean(response.data) == '"Session ended"'

        self.teardown_database()

        del gnucash_rest.app.connection_string

    def test_session(self):
        data = dict(
            connection_string = 'mysql://root:oxford@localhost/test',
            is_new = '1',
            ignore_lock = '0'
        )

        # Logs
        # WARN <gnc.backend.dbi> [gnc_dbi_unlock()] No lock table in database, so not unlocking it.

        # remove the database in case tests failed previously
        self.teardown_database()

        self.setup_database()

        # 201 CREATED
        response = self.app.post('/session', data=data)
        assert self.clean(response.data) == '"Session started"'

        response = self.app.delete('/session')
        assert self.clean(response.data) == '"Session ended"'

        self.teardown_database()

    def test_session_end_error(self):
        assert self.get_error_type('delete', '/session', dict()) == 'SessionDoesNotExist'

    def test_no_method(self):
        assert self.app.open('/session', method='NONE').status == '405 METHOD NOT ALLOWED'
        

class AccountsTestCase(ApiTestCase):

    def test_accounts_no_session(self):
        assert self.get_error_type('get', '/accounts', dict()) == 'SessionDoesNotExist'

    def test_account_get_no_session(self):
        assert self.get_error_type('get', '/accounts/none', dict()) == 'SessionDoesNotExist'

    def test_no_method(self):
        assert self.app.open('/accounts', method='NONE').status == '405 METHOD NOT ALLOWED'

    def test_account_get_splits_no_session(self):
        assert self.get_error_type('get', '/accounts/none/splits', dict()) == 'SessionDoesNotExist'

class AccountsSessionTestCase(ApiTestCase):

    def setUp(self):
        self.app = gnucash_rest.app.test_client()
        self.app.testing = True

        # remove the database in case tests failed previously
        self.teardown_database()

        self.setup_database()

        data = dict(
            connection_string = 'mysql://root:oxford@localhost/test',
            is_new = '1',
            ignore_lock = '0'
        )

        response = self.app.post('/session', data=data)
        assert self.clean(response.data) == '"Session started"'

    def tearDown(self):

        response = self.app.delete('/session')
        assert self.clean(response.data) == '"Session ended"'

        self.teardown_database()

    def test_accounts(self):

        response = json.loads(self.clean(self.app.get('/accounts').data))
        assert response['name'] == 'Root Account'

    # need tests for mangled add accounts

    def test_add_top_account(self):

        response = json.loads(self.clean(self.app.post('/accounts', data=dict(
            name = 'Test',
            currency  = 'GBP',
            account_type_id = '2'
        )).data))

        assert response['name'] == 'Test'

    def test_add_account_no_data(self):

        data = dict()

        assert self.get_error_type('post', '/accounts', data) == 'NoAccountName'

    def test_add_account_no_currency(self):
        data = dict(
            name = 'Test'
        )
        assert self.get_error_type('post', '/accounts', data) == 'InvalidAccountCurrency'

    def test_add_account_invalid_currency(self):

        data = dict(
            name = 'Test',
            currency  = 'XYZ'
        )

        assert self.get_error_type('post', '/accounts', data) == 'InvalidAccountCurrency'

    def test_add_account_invalid_acount_type(self):

        data = dict(
            name = 'Test',
            currency  = 'GBP',
            account_type_id = 'X',
        )

        assert self.get_error_type('post', '/accounts', data) == 'InvalidAccountTypeID'

    def test_add_account(self):

        # this is test_accounts
        response = json.loads(self.clean(self.app.get('/accounts').data))
        assert response['name'] == 'Root Account'

        response = json.loads(self.clean(self.app.post('/accounts', data=dict(
            name = 'Test',
            currency  = 'GBP',
            account_type_id = '2',
            parent_account_guid = response['guid'],
        )).data))

        assert response['name'] == 'Test'

    def test_get_account_none(self):
        assert self.app.get('/accounts/none').status == '404 NOT FOUND'

    def test_add_and_get_account(self):
        account = self.createAccount()

        response = json.loads(self.clean(self.app.get('/accounts/' + account['guid']).data))

        assert response['name'] == 'Test'

    def test_account_get_splits_no_account(self):
        assert self.app.get('/accounts/none/splits').status == '404 NOT FOUND'
    
    def test_account_get_splits_empty(self):
        account = self.createAccount()

        assert json.loads(self.clean(self.app.get('/accounts/' + account['guid'] + '/splits').data)) == []

    # Don't think these are working - lines aren't being tests

    def test_account_get_splits_date_posted_from_empty(self):
        assert self.get_error_type('get', '/accounts/' + self.createAccount()['guid'] + '/splits?date_posted_from=', dict()) == 'InvalidDatePostedFrom'

    def test_account_get_splits_date_posted_from_invalid(self):
        assert self.get_error_type('get', '/accounts/' + self.createAccount()['guid'] + '/splits?date_posted_from=XXX', dict()) == 'InvalidDatePostedFrom'
    def test_account_get_splits_date_posted_from(self):
        assert json.loads(self.clean(self.app.get('/accounts/' + self.createAccount()['guid'] + '/splits?date_posted_from=2010-01-01').data)) == []

    def test_account_get_splits_date_posted_to_empty(self):
        assert self.get_error_type('get', '/accounts/' + self.createAccount()['guid'] + '/splits?date_posted_to=', dict()) == 'InvalidDatePostedTo'

    def test_account_get_splits_date_posted_to_invalid(self):
        assert self.get_error_type('get', '/accounts/' + self.createAccount()['guid'] + '/splits?date_posted_to=XXX', dict()) == 'InvalidDatePostedTo'

    def test_account_get_splits_date_posted_to(self):
        assert json.loads(self.clean(self.app.get('/accounts/' + self.createAccount()['guid'] + '/splits?date_posted_to=2010-01-01').data)) == []

class TransactionsTestCase(ApiTestCase):

    def test_transactions_no_session(self):
        assert self.get_error_type('post', '/transactions', dict()) == 'SessionDoesNotExist'

    def test_transaction_no_session(self):
        assert self.get_error_type('post', '/transactions/none', dict()) == 'SessionDoesNotExist'

class TransactionsSessionTestCase(ApiTestCase):

    def setUp(self):
        self.app = gnucash_rest.app.test_client()
        self.app.testing = True

        # remove the database in case tests failed previously
        self.teardown_database()

        self.setup_database()

        data = dict(
            connection_string = 'mysql://root:oxford@localhost/test',
            is_new = '1',
            ignore_lock = '0'
        )

        response = self.app.post('/session', data=data)
        assert self.clean(response.data) == '"Session started"'

    def tearDown(self):

        response = self.app.delete('/session')
        assert self.clean(response.data) == '"Session ended"'

        self.teardown_database()

    def createTransaction(self):

        # Gnucash does allow a transaction to be across the same accounts so this test is correct!

        # this is test_accounts
        splitaccount1 = json.loads(self.clean(self.app.post('/accounts', data=dict(
            name = 'Test',
            currency  = 'GBP',
            account_type_id = '2'
        )).data))

        splitaccount2 = json.loads(self.clean(self.app.post('/accounts', data=dict(
            name = 'Test 2',
            currency  = 'GBP',
            account_type_id = '2'
        )).data))

        data = dict(
            currency = 'GBP',
            date_posted = '2018-01-01',
            splitaccount1 = splitaccount1['guid'],
            splitaccount2 = splitaccount2['guid'],
            splitvalue1 = '0',
            splitvalue2 = '0'
        )

        return json.loads(self.clean(self.app.post('/transactions', data=data).data))

    def createTransactionGuid(self):
        transaction = self.createTransaction()
        return transaction['guid']

    def test_no_method(self):
        assert self.app.get('/transactions').status == '405 METHOD NOT ALLOWED'

    def test_add_transaction_no_data(self):
        data = dict()
        assert self.get_error_type('post', '/transactions', data) == 'InvalidTransactionCurrency'

    def test_add_transaction_invalid_currency(self):
        data = dict(
            currency = 'XYZ'
        )
        assert self.get_error_type('post', '/transactions', data) == 'InvalidTransactionCurrency'

    def test_add_transaction_no_date_posted(self):
        data = dict(
            currency = 'GBP'
        )
        assert self.get_error_type('post', '/transactions', data) == 'InvalidDatePosted'

    def test_add_transaction_invalid_date_posted(self):
        data = dict(
            currency = 'GBP',
            posted_date = 'XXX'
        )
        assert self.get_error_type('post', '/transactions', data) == 'InvalidDatePosted'

    def test_add_transaction_no_split_account(self):
        data = dict(
            currency = 'GBP',
            date_posted = '2018-01-01'
        )
        assert self.get_error_type('post', '/transactions', data) == 'NoSplits'
    
    def test_add_transaction_single_no_split_value(self):

        # this is test_accounts
        splitaccount1 = json.loads(self.clean(self.app.post('/accounts', data=dict(
            name = 'Test',
            currency  = 'GBP',
            account_type_id = '2'
        )).data))

        data = dict(
            currency = 'GBP',
            date_posted = '2018-01-01',
            splitaccount1 = splitaccount1['guid'],
        )
        assert self.get_error_type('post', '/transactions', data) == 'NoSplits'

    def test_add_transaction_invalid_split_account(self):
        data = dict(
            currency = 'GBP',
            date_posted = '2018-01-01',
            splitvalue1 = '1.5',
            splitaccount1 = 'XXX'
        )
        assert self.get_error_type('post', '/transactions', data) == 'InvalidSplitAccount'

    def test_add_transaction_single_split_account(self):
        # TODO - should this test fail due to only a single split - when we required 2 it failed with InvalidSplitAccount

        # this is test_accounts
        splitaccount1 = json.loads(self.clean(self.app.post('/accounts', data=dict(
            name = 'Test',
            currency  = 'GBP',
            account_type_id = '2'
        )).data))

        data = dict(
            currency = 'GBP',
            date_posted = '2018-01-01',
            splitvalue1 = '1.5',
            splitaccount1 = splitaccount1['guid']
        )

        assert self.app.post('/transactions', data=data).status == '201 CREATED'

    def test_add_transaction_invalid_account_currency(self):

        # this is test_accounts
        splitaccount1 = json.loads(self.clean(self.app.post('/accounts', data=dict(
            name = 'Test',
            currency  = 'GBP',
            account_type_id = '2'
        )).data))

        splitaccount2 = json.loads(self.clean(self.app.post('/accounts', data=dict(
            name = 'Test 2',
            currency  = 'GBP',
            account_type_id = '2'
        )).data))

        data = dict(
            currency = 'EUR',
            date_posted = '2018-01-01',
            splitvalue1 = '1.5',
            splitaccount1 = splitaccount1['guid'],
            splitvalue2 = '1.5',
            splitaccount2 = splitaccount2['guid'],
        )
        assert self.get_error_type('post', '/transactions', data) == 'InvalidSplitAccountCurrency'
    
    def test_add_transaction_identical_split_account(self):
        # Gnucash does allow a transaction to be across the same accounts so this test is correct!

        # this is test_accounts
        splitaccount1 = json.loads(self.clean(self.app.post('/accounts', data=dict(
            name = 'Test',
            currency  = 'GBP',
            account_type_id = '2'
        )).data))

        splitaccount2 = json.loads(self.clean(self.app.post('/accounts', data=dict(
            name = 'Test 2',
            currency  = 'GBP',
            account_type_id = '2'
        )).data))

        data = dict(
            currency = 'GBP',
            date_posted = '2018-01-01',
            splitaccount1 = splitaccount1['guid'],
            splitvalue1 = '1.5',
            splitaccount2 = splitaccount2['guid'],
            splitvalue2 = '1.5',
        )

        # Errors with 20:11:22  CRIT <gnc.backend.dbi> [mysql_error_fn()] DBI error: 1292: Incorrect datetime value: '19700101000000' for column 'reconcile_date' at row 1
        # Due to https://bugzilla.gnome.org/show_bug.cgi?id=784623
        # Worked around by adding the following to mysqld.cnf
        # sql_mode=ONLY_FULL_GROUP_BY,NO_ZERO_IN_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_AUTO_CREATE_USER,NO_ENGINE_SUBSTITUTION

        assert self.app.post('/transactions', data=data).status == '201 CREATED'

    def test_get_transaction_no_transaction(self):

        assert self.app.get('/transactions/none', data=dict()).status == '404 NOT FOUND'

    def test_get_transaction(self):

        # this is test_accounts
        splitaccount1 = json.loads(self.clean(self.app.post('/accounts', data=dict(
            name = 'Test',
            currency  = 'GBP',
            account_type_id = '2'
        )).data))

        splitaccount2 = json.loads(self.clean(self.app.post('/accounts', data=dict(
            name = 'Test 2',
            currency  = 'GBP',
            account_type_id = '2'
        )).data))

        data = dict(
            currency = 'GBP',
            date_posted = '2018-01-01',
            splitaccount1 = splitaccount1['guid'],
            splitvalue1 = '1.5',
            splitaccount2 = splitaccount2['guid'],
            splitvalue2 = '1.5',
            description = 'Test transaction',
            num = '0000001'
        )

        # Errors with 20:11:22  CRIT <gnc.backend.dbi> [mysql_error_fn()] DBI error: 1292: Incorrect datetime value: '19700101000000' for column 'reconcile_date' at row 1
        # Due to https://bugzilla.gnome.org/show_bug.cgi?id=784623
        # Worked around by adding the following to mysqld.cnf
        # sql_mode=ONLY_FULL_GROUP_BY,NO_ZERO_IN_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_AUTO_CREATE_USER,NO_ENGINE_SUBSTITUTION

        response = json.loads(self.clean(self.app.post('/transactions', data=data).data))

        transaction = json.loads(self.clean(self.app.get('/transactions/' +  response['guid'], data=dict()).data))

        assert transaction['description'] == 'Test transaction'

    def test_update_transaction_invalid_guid(self):
        assert self.get_error_type('post', '/transactions/' + '00000000000000000000000000000000', dict()) == 'InvalidTransactionGuid'

    def test_update_transaction_no_data(self):
        assert self.get_error_type('post', '/transactions/' + self.createTransactionGuid(), data=dict()) == 'InvalidTransactionCurrency'

    def test_update_transaction_no_currency(self):
        data = dict(
            currency = 'XYZ'
        )

        assert self.get_error_type('post', '/transactions/' + self.createTransactionGuid(), data=data) == 'InvalidTransactionCurrency'

    def test_update_transaction_invalid_currency(self):
        data = dict(
            currency = 'GBP',
            date_posted = 'XXX'
        )

        assert self.get_error_type('post', '/transactions/' + self.createTransactionGuid(), data=data) == 'InvalidDatePosted'

    def test_update_transaction_no_split_guid(self):
        data = dict(
            currency = 'GBP',
            date_posted = '2018-01-01'
        )
        assert self.get_error_type('post', '/transactions/' + self.createTransactionGuid(), data=data) == 'NoSplits'

    def test_update_transaction_invalid_split_guid(self):
        data = dict(
            currency = 'GBP',
            date_posted = '2018-01-01',
            splitguid1 = 'XXX'
        )
        assert self.get_error_type('post', '/transactions/' + self.createTransactionGuid(), data=data) == 'InvalidSplitGuid'

    def test_update_transaction_no_split_account(self):
        transaction = self.createTransaction()

        data = dict(
            currency = 'GBP',
            date_posted = '2018-01-01',
            splitguid1 = transaction['splits'][0]['guid'],
            splitguid2 = transaction['splits'][0]['guid']
        )

        assert self.get_error_type('post', '/transactions/' + transaction['guid'], data=data) == 'InvalidSplitAccount'

    def test_update_transaction_invalid_split_account(self):
        transaction = self.createTransaction()

        data = dict(
            currency = 'GBP',
            date_posted = '2018-01-01',
            splitguid1 = transaction['splits'][0]['guid'],
            splitguid2 = transaction['splits'][0]['guid'],
            splitaccount1 = 'XXX'
        )

        assert self.get_error_type('post', '/transactions/' + transaction['guid'], data=data) == 'InvalidSplitAccount'

    def test_update_transaction_invalid_split(self):

        # this is test_accounts
        splitaccount1 = json.loads(self.clean(self.app.post('/accounts', data=dict(
            name = 'Test',
            currency  = 'GBP',
            account_type_id = '2'
        )).data))

        splitaccount2 = json.loads(self.clean(self.app.post('/accounts', data=dict(
            name = 'Test 2',
            currency  = 'GBP',
            account_type_id = '2'
        )).data))

        data = dict(
            currency = 'GBP',
            date_posted = '2018-01-01',
            splitaccount1 = splitaccount1['guid'],
            splitaccount2 = splitaccount2['guid'],
            splitguid1 = '00000000000000000000000000000000',
            splitguid2 = '00000000000000000000000000000001'

        )

        assert self.get_error_type('post', '/transactions/' + self.createTransactionGuid(), data=data) == 'InvalidSplitGuid'

    def test_update_transaction_single_invalid_split_account(self):
        transaction = self.createTransaction()

        data = dict(
            currency = 'GBP',
            date_posted = '2018-01-01',
            splitaccount1 = transaction['splits'][0]['account']['guid'],
            splitguid1 = transaction['splits'][0]['guid'],
            splitvalue1 = '1.5',
            splitguid2 = transaction['splits'][0]['guid'],
            splitvalue2 = '1.5'
        )
        
        assert self.get_error_type('post', '/transactions/' + transaction['guid'], data=data) == 'InvalidSplitAccount'

    def test_update_transaction_duplicate_split_guid(self):

        transaction = self.createTransaction()

        data = dict(
            currency = 'GBP',
            date_posted = '2018-01-01',
            splitaccount1 = transaction['splits'][0]['account']['guid'],
            splitaccount2 = transaction['splits'][1]['account']['guid'],
            splitguid1 = transaction['splits'][0]['guid'],
            splitvalue1 = '1.5',
            splitguid2 = transaction['splits'][0]['guid'],
            splitvalue2 = '1.5'
        )

        assert self.get_error_type('post', '/transactions/' + transaction['guid'], data=data) == 'DuplicateSplitGuid'

    def test_update_transaction_no_split_value(self):

        transaction = self.createTransaction()

        data = dict(
            currency = 'GBP',
            date_posted = '2018-01-01',
            splitaccount1 = transaction['splits'][0]['account']['guid'],
            splitaccount2 = transaction['splits'][1]['account']['guid'],
            splitguid1 = transaction['splits'][0]['guid'],
            splitguid2 = transaction['splits'][1]['guid'],
            splitvalue1 = '',

        )

        assert self.get_error_type('post', '/transactions/' + transaction['guid'], data=data) == 'InvalidSplitValue'

    def test_update_transaction_invalid_split_value(self):

        transaction = self.createTransaction()

        data = dict(
            currency = 'GBP',
            date_posted = '2018-01-01',
            splitaccount1 = transaction['splits'][0]['account']['guid'],
            splitaccount2 = transaction['splits'][1]['account']['guid'],
            splitguid1 = transaction['splits'][0]['guid'],
            splitguid2 = transaction['splits'][1]['guid'],
            splitvalue1 = 'A',

        )

        assert self.get_error_type('post', '/transactions/' + transaction['guid'], data=data) == 'InvalidSplitValue'

    def test_update_transaction_no_split_value2(self):

        transaction = self.createTransaction()

        data = dict(
            currency = 'GBP',
            date_posted = '2018-01-01',
            splitaccount1 = transaction['splits'][0]['account']['guid'],
            splitaccount2 = transaction['splits'][1]['account']['guid'],
            splitguid1 = transaction['splits'][0]['guid'],
            splitguid2 = transaction['splits'][1]['guid'],
            splitvalue1 = '0.5',
            splitvalue2 = '',

        )

        assert self.get_error_type('post', '/transactions/' + transaction['guid'], data=data) == 'InvalidSplitValue'

    def test_update_transaction_invalid_split_value2(self):

        transaction = self.createTransaction()

        data = dict(
            currency = 'GBP',
            date_posted = '2018-01-01',
            splitaccount1 = transaction['splits'][0]['account']['guid'],
            splitaccount2 = transaction['splits'][1]['account']['guid'],
            splitguid1 = transaction['splits'][0]['guid'],
            splitguid2 = transaction['splits'][1]['guid'],
            splitvalue1 = '0.5',
            splitvalue2 = 'A',

        )

        assert self.get_error_type('post', '/transactions/' + transaction['guid'], data=data) == 'InvalidSplitValue'

    def test_update_transaction_invalid_account_currency(self):

        transaction = self.createTransaction()

        data = dict(
            currency = 'EUR',
            date_posted = '2018-01-01',
            splitaccount1 = transaction['splits'][0]['account']['guid'],
            splitaccount2 = transaction['splits'][1]['account']['guid'],
            splitguid1 = transaction['splits'][0]['guid'],
            splitguid2 = transaction['splits'][1]['guid'],
            splitvalue1 = '0.5',
            splitvalue2 = '0.5',
        )

        assert self.get_error_type('post', '/transactions/' + transaction['guid'], data=data) == 'InvalidSplitAccountCurrency'
    
    def test_update_transaction(self):

        transaction = self.createTransaction()

        data = dict(
            currency = 'GBP',
            description = 'Updated test transaction',
            date_posted = '2018-01-01',
            splitaccount1 = transaction['splits'][0]['account']['guid'],
            splitaccount2 = transaction['splits'][1]['account']['guid'],
            splitguid1 = transaction['splits'][0]['guid'],
            splitguid2 = transaction['splits'][1]['guid'],
            splitvalue1 = '0.5',
            splitvalue2 = '0.5',

        )

        response = json.loads(self.clean(self.app.post('/transactions/' + transaction['guid'], data=data).data))

        assert response['description'] == 'Updated test transaction'

    def test_delete_transaction_invalid_guid(self):
        assert self.get_error_type('delete', '/transactions/XXX', data=dict()) == 'NoTransaction'

    def test_delete_transaction(self):
        transaction = self.createTransaction()

        self.app.delete('/transactions/' + transaction['guid'], data=dict())

        assert self.app.get('/transactions/' + transaction['guid']).status == '404 NOT FOUND'

class VendorsTestCase(ApiTestCase):

    def test_vendors_no_session(self):
        assert self.get_error_type('get', '/vendors', dict()) == 'SessionDoesNotExist'

    def test_vendor_no_session(self):
        assert self.get_error_type('get', '/vendors/XXX', dict()) == 'SessionDoesNotExist'

    def test_vendor_bills_no_session(self):
        assert self.get_error_type('get', '/vendors/XXX/bills', dict()) == 'SessionDoesNotExist'

class VendorsSessionTestCase(ApiSessionTestCase):

    def test_add_vendor_no_parameters(self):
        assert self.get_error_type('post', '/vendors', dict()) == 'NoVendorName'

    def test_add_vendor_no_address(self):
        data = dict(
            name = 'Test vendor'
        )

        assert self.get_error_type('post', '/vendors', data=data) == 'NoVendorAddress'

    def test_add_vendor_no_currency(self):
        data = dict(
            name = 'Test vendor',
            address_line_1 = 'Test address'
        )

        assert self.get_error_type('post', '/vendors', data=data) == 'InvalidVendorCurrency'

    def test_add_vendor_invalid_currency(self):
        data = dict(
            name = 'Test vendor',
            address_line_1 = 'Test address',
            currency = 'XYZ'
        )

        assert self.get_error_type('post', '/vendors', data=data) == 'InvalidVendorCurrency'

    def test_vendors_no_id(self):

        data = dict(
            name = 'Test vendor',
            address_line_1 = 'Test address',
            currency = 'GBP'
        )

        # Bug 795839 - CustomerNextID() / VendorNextID() output critical gnc.backend.dbi errors 
        # CRIT <gnc.backend.dbi> [error_handler()] DBI error: 1062: Duplicate entry '57696fea5eb84f35a1cbf705d1a868e7' for key 'PRIMARY'
        # CRIT <gnc.backend.dbi> [GncDbiSqlConnection::execute_nonselect_statement()] Error executing SQL INSERT INTO books(guid,root_account_guid,root_template_guid) VALUES('57696fea5eb84f35a1cbf705d1a868e7','7a752878a00349deb0ab83324a9fb6da','a709f4fb7a914301bfe366ce21da9fef')
        # CRIT <gnc.backend.sql> [GncSqlBackend::execute_nonselect_statement()] SQL error: INSERT INTO books(guid,root_account_guid,root_template_guid) VALUES('57696fea5eb84f35a1cbf705d1a868e7','7a752878a00349deb0ab83324a9fb6da','a709f4fb7a914301bfe366ce21da9fef')
        # CRIT <qof.engine> [commit_err()] Failed to commit: 17

        assert self.app.post('/vendors', data=data).status == '201 CREATED'

    def test_vendors_empty_id(self):
        data = dict(
            id = '',
            name = 'Test vendor',
            address_line_1 = 'Test address',
            currency = 'GBP'
        )

        # Bug 795839 - CustomerNextID() / VendorNextID() output critical gnc.backend.dbi errors 
        # CRIT <gnc.backend.dbi> [error_handler()] DBI error: 1062: Duplicate entry '57696fea5eb84f35a1cbf705d1a868e7' for key 'PRIMARY'
        # CRIT <gnc.backend.dbi> [GncDbiSqlConnection::execute_nonselect_statement()] Error executing SQL INSERT INTO books(guid,root_account_guid,root_template_guid) VALUES('57696fea5eb84f35a1cbf705d1a868e7','7a752878a00349deb0ab83324a9fb6da','a709f4fb7a914301bfe366ce21da9fef')
        # CRIT <gnc.backend.sql> [GncSqlBackend::execute_nonselect_statement()] SQL error: INSERT INTO books(guid,root_account_guid,root_template_guid) VALUES('57696fea5eb84f35a1cbf705d1a868e7','7a752878a00349deb0ab83324a9fb6da','a709f4fb7a914301bfe366ce21da9fef')
        # CRIT <qof.engine> [commit_err()] Failed to commit: 17

        assert self.app.post('/vendors', data=data).status == '201 CREATED'

    def test_add_vendor(self):

        data = dict(
            id = '999999',
            name = 'Test vendor',
            address_line_1 = 'Test address',
            currency = 'GBP'
        )

        assert self.app.post('/vendors', data=data).status == '201 CREATED'

    def test_get_vendor_invalid_id(self):
        assert self.app.get('/vendors/999999').status == '404 NOT FOUND'

    def test_get_vendor(self):

        self.createVendor()

        assert json.loads(self.clean(self.app.get('/vendors/999999', data=dict()).data))['id'] == '999999'

    def test_get_vendors(self):

        self.createVendor()

        assert json.loads(self.clean(self.app.get('/vendors', data=dict()).data))[0]['id'] == '999999'

    def test_get_vendor_bills_invalid_id(self):
        assert self.app.get('/vendors/999999/bills').status == '404 NOT FOUND'

    # Need to add a vendor (and probably a bill to do further tests)

    # No checks on vendor / bill options e.g active

    def test_get_empty_vendor_bills(self):

        self.createVendor()

        assert self.clean(self.app.get('/vendors/999999/bills').data) == '[]'

    def test_get_empty_vendors(self):

        assert self.clean(self.app.get('/vendors').data) == '[]'

# Copy of VendorsTestCase with names changed
class CustomersTestCase(ApiTestCase):

    def test_customers_no_session(self):
        assert self.get_error_type('get', '/customers', dict()) == 'SessionDoesNotExist'

    def test_customer_no_session(self):
        assert self.get_error_type('get', '/customers/XXX', dict()) == 'SessionDoesNotExist'

    def test_customer_bills_no_session(self):
        assert self.get_error_type('get', '/customers/XXX/invoices', dict()) == 'SessionDoesNotExist'

# Copy of VendorsSessionTestCase with names changed
class CustomersSessionTestCase(ApiSessionTestCase):

    def test_add_customer_no_parameters(self):
        assert self.get_error_type('post', '/customers', dict()) == 'NoCustomerName'

    def test_add_customer_no_address(self):
        data = dict(
            name = 'Test customer'
        )

        assert self.get_error_type('post', '/customers', data=data) == 'NoCustomerAddress'

    def test_add_customer_no_currency(self):
        data = dict(
            name = 'Test customer',
            address_line_1 = 'Test address'
        )

        assert self.get_error_type('post', '/customers', data=data) == 'InvalidCustomerCurrency'

    def test_add_customer_invalid_currency(self):
        data = dict(
            name = 'Test customer',
            address_line_1 = 'Test address',
            currency = 'XYZ'
        )

        assert self.get_error_type('post', '/customers', data=data) == 'InvalidCustomerCurrency'

    def test_customers_no_id(self):

        data = dict(
            name = 'Test customer',
            address_line_1 = 'Test address',
            currency = 'GBP'
        )

        # Bug 795839 - CustomerNextID() / VendorNextID() output critical gnc.backend.dbi errors 
        # CRIT <gnc.backend.dbi> [error_handler()] DBI error: 1062: Duplicate entry '57696fea5eb84f35a1cbf705d1a868e7' for key 'PRIMARY'
        # CRIT <gnc.backend.dbi> [GncDbiSqlConnection::execute_nonselect_statement()] Error executing SQL INSERT INTO books(guid,root_account_guid,root_template_guid) VALUES('57696fea5eb84f35a1cbf705d1a868e7','7a752878a00349deb0ab83324a9fb6da','a709f4fb7a914301bfe366ce21da9fef')
        # CRIT <gnc.backend.sql> [GncSqlBackend::execute_nonselect_statement()] SQL error: INSERT INTO books(guid,root_account_guid,root_template_guid) VALUES('57696fea5eb84f35a1cbf705d1a868e7','7a752878a00349deb0ab83324a9fb6da','a709f4fb7a914301bfe366ce21da9fef')
        # CRIT <qof.engine> [commit_err()] Failed to commit: 17

        assert self.app.post('/customers', data=data).status == '201 CREATED'

    def test_customers_empty_id(self):
        data = dict(
            id = '',
            name = 'Test customer',
            address_line_1 = 'Test address',
            currency = 'GBP'
        )

        # Bug 795839 - CustomerNextID() / VendorNextID() output critical gnc.backend.dbi errors 
        # CRIT <gnc.backend.dbi> [error_handler()] DBI error: 1062: Duplicate entry '57696fea5eb84f35a1cbf705d1a868e7' for key 'PRIMARY'
        # CRIT <gnc.backend.dbi> [GncDbiSqlConnection::execute_nonselect_statement()] Error executing SQL INSERT INTO books(guid,root_account_guid,root_template_guid) VALUES('57696fea5eb84f35a1cbf705d1a868e7','7a752878a00349deb0ab83324a9fb6da','a709f4fb7a914301bfe366ce21da9fef')
        # CRIT <gnc.backend.sql> [GncSqlBackend::execute_nonselect_statement()] SQL error: INSERT INTO books(guid,root_account_guid,root_template_guid) VALUES('57696fea5eb84f35a1cbf705d1a868e7','7a752878a00349deb0ab83324a9fb6da','a709f4fb7a914301bfe366ce21da9fef')
        # CRIT <qof.engine> [commit_err()] Failed to commit: 17

        assert self.app.post('/customers', data=data).status == '201 CREATED'

    def test_add_customer(self):

        data = dict(
            id = '999999',
            name = 'Test customer',
            address_line_1 = 'Test address',
            currency = 'GBP'
        )

        assert self.app.post('/customers', data=data).status == '201 CREATED'

    def test_get_customer_invalid_id(self):
        assert self.app.get('/customers/999999').status == '404 NOT FOUND'

    def test_get_customer(self):

        self.createCustomer()

        assert json.loads(self.clean(self.app.get('/customers/999999', data=dict()).data))['id'] == '999999'

    def test_get_customers(self):

        self.createCustomer()

        assert json.loads(self.clean(self.app.get('/customers', data=dict()).data))[0]['id'] == '999999'

    def test_get_customer_invoices_invalid_id(self):
        assert self.app.get('/customers/999999/invoices').status == '404 NOT FOUND'

    # Need to add a customer (and probably an invoice to do further tests)

    # No checks on customer / invoice options e.g active

    def test_get_empty_customer_invoices(self):
        self.createCustomer()

        assert self.clean(self.app.get('/customers/999999/invoices').data) == '[]'

    def test_get_empty_customers(self):
        assert self.clean(self.app.get('/customers').data) == '[]'

class InvoicesTestCase(ApiTestCase):

    def test_invoices_no_session(self):
        assert self.get_error_type('get', '/invoices', dict()) == 'SessionDoesNotExist'

    def test_invoice_no_session(self):
        assert self.get_error_type('get', '/invoices/XXXXXX', dict()) == 'SessionDoesNotExist'

class InvoicesSessionTestCase(ApiSessionTestCase):

    def test_add_invoice_no_parameters(self):
        assert self.get_error_type('post', '/invoices', dict()) == 'NoCustomer'

    def test_add_invoice_invalid_customer(self):
        data = dict(
            customer_id = 'XXXXXX',
        )

        assert self.get_error_type('post', '/invoices', data=data) == 'NoCustomer'

    def test_add_invoice_no_date_opened(self):
        data = dict(
            customer_id = self.createCustomer()['id'],
        )

        assert self.get_error_type('post', '/invoices', data=data) == 'InvalidDateOpened'

    def test_add_invoice_empty_date_opened(self):
        data = dict(
            customer_id = self.createCustomer()['id'],
            date_opened = '',
        )

        assert self.get_error_type('post', '/invoices', data=data) == 'InvalidDateOpened'

    def test_add_invoice_invalid_date_opened(self):
        data = dict(
            customer_id = self.createCustomer()['id'],
            date_opened = 'XXX',
        )

        assert self.get_error_type('post', '/invoices', data=data) == 'InvalidDateOpened'

    def test_add_invoice_no_currency(self):
        data = dict(
            customer_id = self.createCustomer()['id'],
            date_opened = '2010-01-01',
        )

        assert self.get_error_type('post', '/invoices', data=data) == 'InvalidInvoiceCurrency'

    def test_add_invoice_invalid_currency(self):
        data = dict(
            customer_id = self.createCustomer()['id'],
            date_opened = '2010-01-01',
            currency = 'XYZ'
        )

        assert self.get_error_type('post', '/invoices', data=data) == 'InvalidInvoiceCurrency'

    def test_add_invoice_non_matching_currency(self):
        data = dict(
            customer_id = self.createCustomer()['id'],
            date_opened = '2010-01-01',
            currency = 'USD' # self.createCustomer() will have GBP
        )

        assert self.get_error_type('post', '/invoices', data=data) == 'MismatchedInvoiceCurrency'

    def test_add_invoice_no_id(self):

        data = dict(
            customer_id = self.createCustomer()['id'],
            date_opened = '2010-01-01',
            currency = 'GBP'
        )

        assert json.loads(self.clean(self.app.post('/invoices', data=data).data))['id'] == '000001'

    def test_add_invoice(self):
        assert self.createInvoice()['id'] == '999999'

    def test_get_invoice_invalid_id(self):
        assert self.app.get('/invoices/999999').status == '404 NOT FOUND'

    def test_get_invoice(self):
        self.createInvoice()

        assert json.loads(self.clean(self.app.get('/invoices/999999').data))['id'] == '999999'

    def test_update_invoice_no_customer(self):
        invoice = self.createInvoice()

        assert self.get_error_type('post', '/invoices/999999', data=dict()) == 'NoCustomer'

    def test_update_invoice_invalid_customer(self):
        invoice = self.createInvoice()

        data = dict(
            customer_id = '888888',
        )
        
        assert self.get_error_type('post', '/invoices/999999', data=data) == 'NoCustomer'

    def test_update_invoice_no_date_opened(self):
        invoice = self.createInvoice()

        data = dict(
            customer_id = self.createCustomer()['id'],
            date_opened = '',
        )

        assert self.get_error_type('post', '/invoices/999999', data=data) == 'InvalidDateOpened'

    def test_update_invoice_invalid_date_opened(self):
        invoice = self.createInvoice()

        data = dict(
            customer_id = self.createCustomer()['id'],
            date_opened = 'XXX',
        )

        assert self.get_error_type('post', '/invoices/999999', data=data) == 'InvalidDateOpened'

    def test_update_invoice(self):
        invoice = self.createInvoice()

        # Why does it need these? Shouldn't one field be enough -it expects all fields rest will be blank

        data = dict(
            customer_id = self.createCustomer()['id'],
            date_opened = '2010-01-01',
        )

        #assert self.get_error_type('post', '/invoices/999999', data=data) == 'NoAccountName'

        assert json.loads(self.clean(self.app.post('/invoices/999999', data=data).data))['id'] == '999999'

        # Do get invoices next e.g /invoice.get

    def test_invoices_no_parameters(self):
        assert self.clean(self.app.get('/invoices').data) == '[]'

    def test_invoices_date_due_from_empty(self):
        assert self.get_error_type('get', '/invoices?date_due_from=', dict()) == 'InvalidDateDueFrom'

    def test_invoices_date_due_from_invalid(self):
        assert self.get_error_type('get', '/invoices?date_due_from=XXX', dict()) == 'InvalidDateDueFrom'

    def test_invoices_date_due_from(self):
        assert self.clean(self.app.get('/invoices?date_due_from=2010-01-01').data) == '[]'

    def test_invoices_date_due_to_empty(self):
        assert self.get_error_type('get', '/invoices?date_due_to=', dict()) == 'InvalidDateDueTo'

    def test_invoices_date_due_to_invalid(self):
        assert self.get_error_type('get', '/invoices?date_due_to=XXX', dict()) == 'InvalidDateDueTo'

    def test_invoices_date_due_to(self):
        assert self.clean(self.app.get('/invoices?date_due_to=2010-01-01').data) == '[]'

    def test_invoices_date_opened_from_empty(self):
        assert self.get_error_type('get', '/invoices?date_opened_from=', dict()) == 'InvalidDateOpenedFrom'

    def test_invoices_date_opened_from_invalid(self):
        assert self.get_error_type('get', '/invoices?date_opened_from=XXX', dict()) == 'InvalidDateOpenedFrom'

    def test_invoices_date_opened_from(self):
        assert self.clean(self.app.get('/invoices?date_opened_from=2010-01-01').data) == '[]'

    def test_invoices_date_opened_to_empty(self):
        assert self.get_error_type('get', '/invoices?date_opened_to=', dict()) == 'InvalidDateOpenedTo'

    def test_invoices_date_opened_to_invalid(self):
        assert self.get_error_type('get', '/invoices?date_opened_to=XXX', dict()) == 'InvalidDateOpenedTo'

    def test_invoices_date_opened_to(self):
        assert self.clean(self.app.get('/invoices?date_opened_to=2010-01-01').data) == '[]'

    def test_invoices_date_posted_from_empty(self):
        assert self.get_error_type('get', '/invoices?date_posted_from=', dict()) == 'InvalidDatePostedFrom'

    def test_invoices_date_posted_from_invalid(self):
        assert self.get_error_type('get', '/invoices?date_posted_from=XXX', dict()) == 'InvalidDatePostedFrom'

    def test_invoices_date_posted_from(self):
        assert self.clean(self.app.get('/invoices?date_posted_from=2010-01-01').data) == '[]'

    def test_invoices_date_posted_to_empty(self):
        assert self.get_error_type('get', '/invoices?date_posted_to=', dict()) == 'InvalidDatePostedTo'

    def test_invoices_date_posted_to_invalid(self):
        assert self.get_error_type('get', '/invoices?date_posted_to=XXX', dict()) == 'InvalidDatePostedTo'

    def test_invoices_date_posted_to(self):
        assert self.clean(self.app.get('/invoices?date_posted_to=2010-01-01').data) == '[]'

class BillsTestCase(ApiTestCase):

    def test_bills_no_session(self):
        assert self.get_error_type('get', '/bills', dict()) == 'SessionDoesNotExist'

# This is identical to invoices....
class BillsSessionTestCase(ApiSessionTestCase):

    def test_bills_no_parameters(self):
        assert self.clean(self.app.get('/bills').data) == '[]'

    def test_bills_no_parameters(self):
        assert self.clean(self.app.get('/bills').data) == '[]'

    def test_bills_date_due_from_empty(self):
        assert self.get_error_type('get', '/bills?date_due_from=', dict()) == 'InvalidDateDueFrom'

    def test_bills_date_due_from_invalid(self):
        assert self.get_error_type('get', '/bills?date_due_from=XXX', dict()) == 'InvalidDateDueFrom'

    def test_bills_date_due_from(self):
        assert self.clean(self.app.get('/bills?date_due_from=2010-01-01').data) == '[]'

    def test_bills_date_due_to_empty(self):
        assert self.get_error_type('get', '/bills?date_due_to=', dict()) == 'InvalidDateDueTo'

    def test_bills_date_due_to_invalid(self):
        assert self.get_error_type('get', '/bills?date_due_to=XXX', dict()) == 'InvalidDateDueTo'

    def test_bills_date_due_to(self):
        assert self.clean(self.app.get('/bills?date_due_to=2010-01-01').data) == '[]'

    def test_bills_date_opened_from_empty(self):
        assert self.get_error_type('get', '/bills?date_opened_from=', dict()) == 'InvalidDateOpenedFrom'

    def test_bills_date_opened_from_invalid(self):
        assert self.get_error_type('get', '/bills?date_opened_from=XXX', dict()) == 'InvalidDateOpenedFrom'

    def test_bills_date_opened_from(self):
        assert self.clean(self.app.get('/bills?date_opened_from=2010-01-01').data) == '[]'

    def test_bills_date_opened_to_empty(self):
        assert self.get_error_type('get', '/bills?date_opened_to=', dict()) == 'InvalidDateOpenedTo'

    def test_bills_date_opened_to_invalid(self):
        assert self.get_error_type('get', '/bills?date_opened_to=XXX', dict()) == 'InvalidDateOpenedTo'

    def test_bills_date_opened_to(self):
        assert self.clean(self.app.get('/bills?date_opened_to=2010-01-01').data) == '[]'

    def test_bills_date_posted_from_empty(self):
        assert self.get_error_type('get', '/bills?date_posted_from=', dict()) == 'InvalidDatePostedFrom'

    def test_bills_date_posted_from_invalid(self):
        assert self.get_error_type('get', '/bills?date_posted_from=XXX', dict()) == 'InvalidDatePostedFrom'

    def test_bills_date_posted_from(self):
        assert self.clean(self.app.get('/bills?date_posted_from=2010-01-01').data) == '[]'

    def test_bills_date_posted_to_empty(self):
        assert self.get_error_type('get', '/bills?date_posted_to=', dict()) == 'InvalidDatePostedTo'

    def test_bills_date_posted_to_invalid(self):
        assert self.get_error_type('get', '/bills?date_posted_to=XXX', dict()) == 'InvalidDatePostedTo'

    def test_bills_date_posted_to(self):
        assert self.clean(self.app.get('/bills?date_posted_to=2010-01-01').data) == '[]'

    # add_bill
    #def test_bills(self):
    #    print self.app.post('/bills').data

    #def test_bills(self):
    #    print self.app.get('/bills?is_paid=X').data

if __name__ == '__main__':
    unittest.main()