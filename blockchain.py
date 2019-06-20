from functools import reduce
import hashlib as hl

import json
import pickle

from hash_util import hash_block
from block import Block
from transaction import Transaction
from verification import Verification

# Global Variables --------------------------------------------
MINING_REWARD = 10

class Blockchain:
# Constructor -------------------------------------------------------
    def __init__(self, hosting_node_id):
        genesis_block = Block(0, '', [], 100, 0)
        self.chain = [genesis_block]
        self.__open_transactions = []
        self.load_data()
        self.hosting_node = hosting_node_id

# Getter und Setter ------------------------------------------------
    @property
    def chain(self):
        return self.__chain[:] # Nur Kopie wird zurückgegeben durch [:].

    @chain.setter
    def chain(self, val):
        self.__chain = val

# Methods --------------------------------------------------------

    def get_open_transactions(self):
        return self.__open_transactions[:] # Nur Kopie wird zurückgegeben durch [:].

    def load_data(self):
        try:
            # with open('blockchain.p', mode='rb') as f:
                # file_content = pickle.loads(f.read())
                # blockchain = file_content['chain']
                # open_transactions = file_content['ot']
            with open('blockchain.txt', mode='r') as f:
                file_content = f.readlines()
                blockchain = json.loads(file_content[0][:-1])
                # We need to convert  the loaded data because Transactions should use OrderedDict
                updated_blockchain = []
                for block in blockchain:
                    converted_tx = [Transaction(tx['sender'], tx['recipient'], tx['amount']) for tx in block['transactions']]
                    updated_block = Block(block['index'], block['previous_hash'], converted_tx, block['proof'], block['timestamp'])

                    updated_blockchain.append(updated_block)
                self.chain = updated_blockchain
                open_transactions = json.loads(file_content[1])
                # We need to convert  the loaded data because Transactions should use OrderedDict
                updated_transactions = []
                for tx in open_transactions:
                    updated_transaction = Transaction(tx['sender'], tx['recipient'], tx['amount'])
                    updated_transactions.append(updated_transaction)
                self.__open_transactions = updated_transactions
        except (IOError, IndexError):
            print('IOError or IndexError on Blockchain!')
        finally:
            # Cleanup-Code
            pass

    def save_data(self):
        """Save blockchain + open transactions snapshot to a file."""
        try:
            with open('blockchain.txt', mode='w') as f:
                saveable_chain = [block.__dict__ for block in [Block(block_el.index, block_el.previous_hash, [tx.__dict__ for tx in block_el.transactions], block_el.proof, block_el.timestamp) for block_el in self.__chain]]
                f.write(json.dumps(saveable_chain))
                f.write('\n')
                saveable_tx = [tx.__dict__ for tx in self.__open_transactions]
                f.write(json.dumps(saveable_tx))
                # save_data = {
                #     'chain': blockchain,
                #     'ot': open_transactions
                # }
                # f.write(pickle.dumps(save_data))
        except IOError:
            print('Saving failed!')

    def proof_of_work(self):
        last_block = self.__chain[-1]
        last_hash = hash_block(last_block)
        proof = 0
        while not Verification.valid_proof(self.__open_transactions, last_hash, proof):
            proof += 1
        return proof

    def get_balance(self):

        participant = self.hosting_node
        # Es werden alle Werte 'amount' jedes blocks ausgegeben, bei welchem der übergebene participant der sender war.
        tx_sender = [[tx.amount for tx in block.transactions if tx.sender == participant] for block in self.__chain]
        open_tx_sender = [tx.amount for tx in self.__open_transactions if tx.sender == participant]
        tx_sender.append(open_tx_sender)

        # gesendete Menge zählen mit reduce alternative
        amount_sent = reduce(lambda tx_sum, tx_amt: tx_sum + sum(tx_amt) if len(tx_amt) > 0 else tx_sum + 0, tx_sender, 0)
        # amount_sent = 0
        # for tx in tx_sender:
        #     if len(tx) > 0:
        #         amount_sent += tx[0]

        tx_recipient = [[tx.amount for tx in block.transactions if tx.recipient == participant] for block in self.__chain]
        
        # erhaltenen Menge zählen mit reduce alternative
        amount_received = reduce(lambda tx_sum, tx_amt: tx_sum + sum(tx_amt) if len(tx_amt) > 0 else tx_sum + 0, tx_recipient, 0)
        # amount_received = 0
        # for tx in tx_recipient:
        #     if len(tx) > 0:
        #         amount_received += tx[0]

        return amount_received - amount_sent

    def get_last_blockchain_value(self):
        if len(self.__chain) < 1:
            return None
        return self.__chain[-1]

    def add_transaction(self, recipient, sender, amount = 1.0):
        """Append a new transaction

        Arguments:
        :sender:
        :recipient:
        :amount:
        """
        # transaction = {
        #     'sender': sender,
        #     'recipient': recipient, 
        #     'amount': amount
        # }
        transaction = Transaction(sender, recipient, amount)
        # get_balance ist eine Funktion, ohne Klammern heißt sie wird als Referenz übergeben, wo sie dann
        # in verify_transaction aufgerufen werden kann.
        if Verification.verify_transaction(transaction, self.get_balance):
            self.__open_transactions.append(transaction)
            self.save_data()
            return True
        return False


    def mine_block(self):
        last_block = self.__chain[-1]
        hashed_block = hash_block(last_block)
        proof = self.proof_of_work()
        # reward_transaction = {
        #     'sender': 'MINING',
        #     'recipient': owner,
        #     'amount': MINING_REWARD
        # }
        reward_transaction = Transaction('MINING', self.hosting_node, MINING_REWARD)
        copied_transactions = self.__open_transactions[:]
        copied_transactions.append(reward_transaction)
        # block wird noch als nicht geordnete Liste deklariert, um sort_keys=True als Parameter zu json.dumps() zu demonstrieren. 
        # siehe Funktion hash_block
        block = Block(len(self.__chain), hashed_block, copied_transactions, proof)

        self.__chain.append(block)
        self.__open_transactions = []
        self.save_data()
        return True

# Code --------------------------------------------------------
