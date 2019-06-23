from functools import reduce
import hashlib as hl

import json
import pickle
import requests

from utility.hash_util import hash_block
from utility.verification import Verification
from block import Block
from transaction import Transaction
from wallet import Wallet

# Global Variables --------------------------------------------
MINING_REWARD = 10

class Blockchain:
# Constructor -------------------------------------------------------
    def __init__(self, public_key, node_id):
        genesis_block = Block(0, '', [], 100, 0)
        self.chain = [genesis_block]
        self.__open_transactions = []
        self.public_key = public_key
        self.__peer_nodes = set()
        self.node_id = node_id
        self.resolve_conflicts = False
        self.load_data()

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
            with open('blockchain-{}.txt'.format(self.node_id), mode='r') as f:
                file_content = f.readlines()
                blockchain = json.loads(file_content[0][:-1])
                # Konvertieren der Daten zu einem OrderedDict.
                updated_blockchain = []
                for block in blockchain:
                    converted_tx = [Transaction(tx['sender'], tx['recipient'], tx['signature'], tx['amount']) for tx in block['transactions']]
                    updated_block = Block(block['index'], block['previous_hash'], converted_tx, block['proof'], block['timestamp'])

                    updated_blockchain.append(updated_block)
                self.chain = updated_blockchain
                open_transactions = json.loads(file_content[1][:-1])
                # Konvertieren der Daten zu einem OrderedDict.
                updated_transactions = []
                for tx in open_transactions:
                    updated_transaction = Transaction(tx['sender'], tx['recipient'], tx['signature'], tx['amount'])
                    updated_transactions.append(updated_transaction)
                self.__open_transactions = updated_transactions
                peer_nodes = json.loads(file_content[2])
                self.__peer_nodes = set(peer_nodes)
        except (IOError, IndexError):
            print('IOError or IndexError on Blockchain!')
        finally:
            # Cleanup-Code
            pass

    def save_data(self):
        """Save blockchain + open transactions snapshot to a file."""
        try:
            with open('blockchain-{}.txt'.format(self.node_id), mode='w') as f:
                saveable_chain = [block.__dict__ for block in [Block(block_el.index, block_el.previous_hash, [tx.__dict__ for tx in block_el.transactions], block_el.proof, block_el.timestamp) for block_el in self.__chain]]
                f.write(json.dumps(saveable_chain))
                f.write('\n')
                saveable_tx = [tx.__dict__ for tx in self.__open_transactions]
                f.write(json.dumps(saveable_tx))
                f.write('\n')
                f.write(json.dumps(list(self.__peer_nodes)))
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

    def get_balance(self, sender=None):

        if sender == None:
            if self.public_key == None:
                return None
            participant = self.public_key
        else:
            participant = sender
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

    def add_transaction(self, recipient, sender, signature,  amount = 1.0, is_receiving=False):
        """Append a new transaction

        Arguments:
        :sender: The sender of the coins.
        :recipient: The recipient of the coins.
        :amount: The amount of coins to be sent (default = 1.0)
        :is_receiving: Ist die Node nur ein Empfänger?
        """
        # Überprüfung, ob Wallet korrekt initialisiert.
        # Es kann sein, wenn eine Transaktion an eine andere Node gesendet wird,
        # und diese nicht korrekt initalisiert ist, dass er auch hier return false zurückgibt.
        # Fehler muss noch behoben werden!!!
        if self.public_key == None:
            return False

        transaction = Transaction(sender, recipient, signature, amount)
        # get_balance ist eine Funktion, ohne Klammern heißt sie wird als Referenz übergeben, wo sie dann
        # in verify_transaction aufgerufen werden kann.
        if Verification.verify_transaction(transaction, self.get_balance):
            self.__open_transactions.append(transaction)
            self.save_data()
            # Hier folgt der Broadcast zu den anderen Nodes.
            # Soll nur durch die Node ausgelöst werden, welche die Transaction erstellt. 
            # Ansonsten würde es zu einem Endlosloop kommen, da jede Node die Transaktion hinzufügen würde,
            # und sie dann wieder broadcasted.
            if not is_receiving: 
                for node in self.__peer_nodes:
                    url = 'http://{}/broadcast-transaction'.format(node)
                    try:
                        response = requests.post(url, json={'sender':sender, 'recipient': recipient, 'amount': amount, 'signature': signature})
                        if response.status_code == 400 or response.status_code == 500:
                            print('Transaction declined, needs resolving')
                            return False
                    except requests.exceptions.ConnectionError:
                            continue
            return True
        return False


    def mine_block(self):
        if self.public_key == None:
            return None
        last_block = self.__chain[-1]
        hashed_block = hash_block(last_block)
        proof = self.proof_of_work()

        reward_transaction = Transaction('MINING', self.public_key, '', MINING_REWARD)
        copied_transactions = self.__open_transactions[:]

        for tx in copied_transactions:
            if not Wallet.verify_transaction(tx):
                return None

        copied_transactions.append(reward_transaction)
        # block wird noch als nicht geordnete Liste deklariert, um sort_keys=True als Parameter zu json.dumps() zu demonstrieren. 
        # siehe Funktion hash_block
        block = Block(len(self.__chain), hashed_block, copied_transactions, proof)

        self.__chain.append(block)
        self.__open_transactions = []
        self.save_data()
        for node in self.__peer_nodes:
            url = 'http://{}/broadcast-block'.format(node)
            converted_block = block.__dict__.copy()
            converted_block['transactions'] = [tx.__dict__ for tx in converted_block['transactions']]
            try:
                response = requests.post(url, json={'block': converted_block})
                if response.status_code == 400 or response.status_code == 500:
                    print('Block declined, needs resolving')
                if response.status_code == 409:
                    self.resolve_conflicts = True
            except requests.exceptions.ConnectionError:
                continue
        return block

    def add_block(self, block):
        transactions = [Transaction(tx['sender'], tx['recipient'], tx['signature'], tx['amount']) for tx in block['transactions']]
        proof_is_valid = Verification.valid_proof(transactions[:-1], block['previous_hash'], block['proof'])
        hashes_match = hash_block(self.chain[-1]) == block['previous_hash']
        if not proof_is_valid or not hashes_match:
            return False
        converted_block = Block(block['index'], block['previous_hash'], transactions, block['proof'], block['timestamp'])
        self.__chain.append(converted_block)
        stored_transactions = self.__open_transactions[:]
        for incoming_tx in block['transactions']:
            for open_tx in stored_transactions:
                if open_tx.sender == incoming_tx['sender'] and open_tx.recipient == incoming_tx['recipient'] and open_tx.amount == incoming_tx['amount'] and open_tx.signature == incoming_tx['signature']:
                    try:
                        self.__open_transactions.remove(open_tx)
                    except ValueError:
                        print('Item was already removed.')
        self.save_data()
        return True

    def resolve(self):
        winner_chain = self.chain
        replace = False
        for node in self.__peer_nodes:
            url = 'http://{}/chain'.format(node)
            try:
                response = requests.get(url)
                node_chain = response.json()
                node_chain = [Block(block['index'], block['previous_hash'], [Transaction(
                    tx['sender'], tx['recipient'], tx['signature'], tx['amount']) for tx in block['transactions']],
                    block['proof'], block['timestamp']) for block in node_chain]
                node_chain_length = len(node_chain)
                local_chain_length = len(self.chain)
                if node_chain_length > local_chain_length and Verification.verify_chain(node_chain):
                    winner_chain = node_chain
                    replace = True
            except requests.exceptions.ConnectionError:
                continue
        self.resolve_conflicts = False
        self.chain = winner_chain
        if replace:
            self.__open_transactions = []
        self.save_data()
        return replace

    def add_peer_node(self, node):
        """Adds a new node to the peer node set.

        Arguments:
            :node: The node URL which should be added.
        """
        self.__peer_nodes.add(node)
        self.save_data()

    def remove_peer_node(self, node):
        """Removes a node from the peer node set.

        Arguments:
            :node: The node URL which should be added.
        """
        self.__peer_nodes.discard(node)
        self.save_data()

    def get_peer_nodes(self):
        """Return a list of all connected peer nodes."""
        return list(self.__peer_nodes)
# Code --------------------------------------------------------
