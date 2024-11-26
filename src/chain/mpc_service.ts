import { createWalletClient, http, type Account } from 'viem'
import { mainnet } from 'viem/chains'

interface TransactionParams {
  from: string;
  to: string;
  value: bigint;
  data?: string;
}

export class MPCService {
  private walletClient: any;

  constructor(config: { apiKey: string; network: string }) {
    this.walletClient = createWalletClient({
      chain: mainnet,
      transport: http()
    })
  }

  async sendTransaction(params: TransactionParams) {
    const tx = await this.walletClient.sendTransaction({
      ...params,
      account: params.from as Account
    })
    return tx
  }

  async createTBA(owner: string, implementation: string) {
    // TODO: Implement ERC-6551 account creation
    throw new Error('Not implemented')
  }
} 