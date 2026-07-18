import Constants from "expo-constants";

const API_URL =
  (Constants.expoConfig?.extra?.apiUrl as string) || "http://127.0.0.1:5000/api/v1";

let authToken: string | null = null;

export function setToken(token: string | null) {
  authToken = token;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (authToken) {
    headers.Authorization = `Bearer ${authToken}`;
  }

  const response = await fetch(`${API_URL}${path}`, { ...options, headers });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Request failed");
  }
  return data as T;
}

export const api = {
  health: () => request<{ status: string; stripe: boolean }>("/health"),
  meta: () => request<{
    app: AppMeta;
    plans: Record<string, unknown>;
    currencies: Record<string, unknown>;
  }>("/meta"),
  register: (body: { name: string; email: string; password: string; currency?: string }) =>
    request<{ token: string; user: User }>("/auth/register", { method: "POST", body: JSON.stringify(body) }),
  login: (body: { email: string; password: string }) =>
    request<{ token: string; user: User }>("/auth/login", { method: "POST", body: JSON.stringify(body) }),
  me: () => request<{ user: User }>("/me"),
  dashboard: () => request<DashboardData>("/dashboard"),
  transactions: () => request<{ transactions: Transaction[] }>("/transactions"),
  createTransaction: (body: Partial<Transaction>) =>
    request<{ transaction: Transaction }>("/transactions", { method: "POST", body: JSON.stringify(body) }),
  accounts: () => request<{ accounts: Account[] }>("/accounts"),
  budgets: () => request<{ budgets: Budget[] }>("/budgets"),
  goals: () => request<{ goals: Goal[] }>("/goals"),
  verifyMobilePurchase: (body: {
    provider: "apple" | "google";
    product_id: string;
    transaction_id: string;
    purchase_token?: string;
    receipt_data?: string;
    expires_at?: string;
  }) => request<{ message: string; user: User }>("/billing/mobile/verify", { method: "POST", body: JSON.stringify(body) }),
  deleteMe: () => request<{ ok: boolean }>("/me", { method: "DELETE" }),

  // Banking API
  bankingSummary: () => request<BankingSummary>("/banking/summary"),
  bankingBanks: (q?: string) => request<{ banks: BankInfo[] }>(`/banking/banks${q ? `?q=${q}` : ""}`),
  bankingConnect: (body: { bank_name: string; account_number: string; ifsc: string; account_type?: string }) =>
    request<{ connection_id: number; account_id: number; upi_id: string; message: string; transactions_imported: number }>("/banking/connect", { method: "POST", body: JSON.stringify(body) }),
  bankingConnections: () => request<{ connections: BankConnection[]; upi_ids: UpiId[] }>("/banking/connections"),
  bankingSync: (connectionId: number) => request<{ synced: number; new_balance: number; message: string }>(`/banking/connections/${connectionId}/sync`),
  bankingDisconnect: (connectionId: number) => request<{ ok: boolean }>(`/banking/connections/${connectionId}`, { method: "DELETE" }),
  bankingBeneficiaries: () => request<{ beneficiaries: Beneficiary[] }>("/banking/beneficiaries"),
  bankingAddBeneficiary: (body: { name: string; account_number?: string; ifsc?: string; upi_id?: string; bank_name?: string }) =>
    request<{ beneficiary: Beneficiary }>("/banking/beneficiaries", { method: "POST", body: JSON.stringify(body) }),
  bankingTransfer: (body: { from_account_id: number; beneficiary_id?: number; beneficiary_name?: string; beneficiary_account?: string; beneficiary_ifsc?: string; amount: number; reference?: string }) =>
    request<{ transfer_id: number; utr: string; status: string; message: string }>("/banking/transfer", { method: "POST", body: JSON.stringify(body) }),
  bankingUpiPay: (body: { to_upi_id: string; amount: number; note?: string }) =>
    request<{ payment_id: number; txn_id: string; utr: string; message: string }>("/banking/upi/pay", { method: "POST", body: JSON.stringify(body) }),
  bankingUpiQr: (amount?: number, note?: string) =>
    request<{ upi_id: string; qr_string: string; amount: number; note: string }>(`/banking/upi/qr${amount ? `?amount=${amount}&note=${note || "Payment"}` : ""}`),
  bankingBillers: (category?: string) => request<{ billers?: Biller[]; categories?: Record<string, string> }>(`/banking/billers${category ? `?category=${category}` : ""}`),
  bankingFetchBill: (body: { biller_code: string; consumer_number: string }) =>
    request<{ bill: BillData }>("/banking/bills/fetch", { method: "POST", body: JSON.stringify(body) }),
  bankingPayBill: (body: { biller_code: string; biller_name: string; consumer_number: string; amount: number; from_account_id: number }) =>
    request<{ payment_id: number; reference: string; status: string; message: string }>("/bills/pay", { method: "POST", body: JSON.stringify(body) }),
  bankingTransfers: () => request<{ transfers: PaymentTransfer[] }>("/banking/transfers"),
  bankingUpiPayments: () => request<{ payments: UpiPayment[] }>("/banking/upi/payments"),
  bankingBillHistory: () => request<{ bills: BillPayment[] }>("/banking/bills/history"),
  bankingIfscLookup: (ifsc: string) => request<{ ifsc: IfscDetails }>(`/banking/ifsc/${ifsc}`),
  bankingVerifyAccount: (body: { account_number: string; ifsc: string }) =>
    request<{ verified: boolean; account_holder: string }>("/banking/verify-account", { method: "POST", body: JSON.stringify(body) }),
};

export type AppMeta = {
  name: string;
  support_email: string;
  privacy_url: string;
  terms_url: string;
};

export type User = {
  id: number;
  name: string;
  email: string;
  plan: string;
  effective_plan?: string;
  subscription_status: string;
  currency: string;
  features?: string[];
};

export type DashboardData = {
  total_income: number;
  total_expenses: number;
  balance: number;
  net_worth: number;
  monthly_income: number;
  monthly_expenses: number;
  monthly_net: number;
  currency: string;
  recent_transactions: Transaction[];
};

export type Transaction = {
  id: number;
  description: string;
  amount: number;
  category: string;
  type: "income" | "expense";
  transaction_date: string;
  account_name?: string;
};

export type Account = {
  id: number;
  name: string;
  type: string;
  balance: number;
};

export type Budget = {
  id: number;
  category: string;
  monthly_limit: number;
  spent: number;
};

export type Goal = {
  id: number;
  name: string;
  target_amount: number;
  current_amount: number;
  deadline?: string;
};

// Banking types
export type BankingSummary = {
  connected_banks: number;
  connections: BankConnection[];
  upi_ids: UpiId[];
  recent_transfers: PaymentTransfer[];
  recent_bills: BillPayment[];
  beneficiaries: Beneficiary[];
};

export type BankInfo = {
  name: string;
  logo: string;
};

export type BankConnection = {
  id: number;
  user_id: number;
  bank_name: string;
  account_number: string;
  ifsc: string;
  account_type: string;
  status: string;
  consent_id?: string;
  last_synced?: string;
  created_at: string;
  balance?: number;
};

export type UpiId = {
  id: number;
  user_id: number;
  upi_id: string;
  bank_name: string;
  is_primary: number;
  created_at: string;
};

export type Beneficiary = {
  id: number;
  user_id: number;
  name: string;
  account_number: string;
  ifsc: string;
  upi_id?: string;
  bank_name?: string;
  verified: number;
  favorite: number;
  added_at: string;
};

export type PaymentTransfer = {
  id: number;
  user_id: number;
  from_account_id: number;
  beneficiary_name: string;
  beneficiary_account: string;
  beneficiary_ifsc: string;
  amount: number;
  status: string;
  utr?: string;
  reference?: string;
  initiated_at: string;
  from_account_name?: string;
};

export type UpiPayment = {
  id: number;
  user_id: number;
  from_upi_id: string;
  to_upi_id: string;
  amount: number;
  note: string;
  status: string;
  txn_id?: string;
  utr?: string;
  created_at: string;
};

export type BillPayment = {
  id: number;
  user_id: number;
  from_account_id: number;
  biller_code: string;
  biller_name: string;
  consumer_number: string;
  amount: number;
  status: string;
  reference?: string;
  paid_at: string;
  account_name?: string;
};

export type Biller = {
  name: string;
  biller_code: string;
  logo: string;
};

export type BillData = {
  biller_code: string;
  consumer_number: string;
  amount: number;
  due_date: string;
  biller_name: string;
  bill_period: string;
};

export type IfscDetails = {
  bank: string;
  branch: string;
  city: string;
  ifsc: string;
  micr: string;
};
