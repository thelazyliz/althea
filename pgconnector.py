import psycopg2
import logging
from psycopg2.extras import RealDictCursor

insert_logger = logging.getLogger('stream.py')


class PostgresConnector:
    def __init__(self, dbpath):
        self._conn = psycopg2.connect(dbpath)
        self._cur = self._conn.cursor(cursor_factory=RealDictCursor)

    def execute(self, query):
        self._cur.execute(query)
        return self._cur.fetchall()

    def get_all_from_table(self, table):
        self._cur.execute(f'select * from {table};')
        return self._cur.fetchall()

    def get_positions(self, chat_id, username=None, coin=None,
                      open_only=False, close_only=False, id=None):
        if open_only and close_only:
            raise SyntaxError('Both open_only and close_only cannot be true!')
        init_query = f'select * from positions where chat_id = {chat_id}'
        if id:
            init_query += f' and id = {id}'
        if username:
            init_query += f' and username = {username}'
        if coin:
            init_query += f' and coin = {coin}'
        if open_only:
            init_query += f' and close_price isnull'
        if close_only:
            init_query += f' and close_price notnull'
        self._cur.execute(f'{init_query};')
        return self._cur.fetchall()

    def insert_position(self, insert_list):
        '''
        :param insert_list: in the order
        [username, coin, open_price, open_time, open_recorded_by, chat_id]
        :return:
        '''
        query = '''
            insert into positions (username, coin, open_price, open_time, 
            open_recorded_by, chat_id) 
            values (%s, %s, %s, %s, to_timestamp(%s), %s);
        '''
        try:
            self._cur.execute(query, insert_list)
            if self._cur.rowcount == 0:
                self._conn.rollback()
                insert_logger.debug(
                    f'failed to insert {",".join(insert_list)}'
                )
                return False
            else:
                self._conn.commit()
                insert_logger.debug(f'inserted {",".join(insert_list)}')
                return True
        except Exception as e:
            self._conn.rollback()
            insert_logger.info(
                f'exception occurred with {",".join(insert_list)}'
            )
            insert_logger.exception(str(e))
            return False

    def close_position(self, id, close_list):
        query = '''
            update positions set close_price = %s, close_time = %s, 
            close_recorded_by = to_timestamp(%s), return_rate = %s 
            where id = %s;
        '''
        try:
            self._cur.execute(query, (*close_list, id))
            if self._cur.rowcount == 0:
                self._conn.rollback()
                insert_logger.debug(
                    f'failed to update {id}'
                )
                return False
            else:
                self._conn.commit()
                insert_logger.debug(f'updated {id}')
                return True
        except Exception as e:
            self._conn.rollback()
            insert_logger.info(
                f'exception occurred with {id}'
            )
            insert_logger.exception(str(e))
            return False

    def close(self):
        self._cur.close()
        self._conn.close()
