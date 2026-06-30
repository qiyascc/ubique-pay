"""TON treasury wallet helper.

    python manage.py ton_wallet            # derive address from TON_MNEMONIC
    python manage.py ton_wallet --create   # generate a fresh TESTNET wallet

Fund a testnet wallet at https://t.me/testgiver_ton_bot, set its mnemonic as
TON_MNEMONIC (and TON_TESTNET=1), then real USDT-TON transfers run through the
TonChainSender adapter.
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Show the TON treasury address or create a new testnet wallet."

    def add_arguments(self, parser):
        parser.add_argument("--create", action="store_true",
                            help="Generate a new testnet wallet (prints mnemonic).")

    def handle(self, *args, **options):
        if options["create"]:
            from tonutils.clients import ToncenterClient
            from tonutils.clients.base import NetworkGlobalID
            from tonutils.contracts.wallet import WalletV4R2

            client = ToncenterClient(NetworkGlobalID.TESTNET)
            wallet, _pub, _priv, words = WalletV4R2.create(client)
            self.stdout.write(self.style.SUCCESS("New TESTNET wallet:"))
            self.stdout.write(f"  address:  {wallet.address}")
            self.stdout.write(f"  mnemonic: {' '.join(words)}")
            self.stdout.write("Fund it: https://t.me/testgiver_ton_bot")
            return

        from ubique.providers.real import TonChainSender

        sender = TonChainSender()
        net = "testnet" if sender.is_testnet else "mainnet"
        self.stdout.write(self.style.SUCCESS(f"Treasury wallet ({net}):"))
        self.stdout.write(f"  address: {sender.treasury_address()}")
        self.stdout.write(f"  USDT jetton master: {sender.master}")
