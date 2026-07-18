import React, { useEffect, useState } from "react";
import { ActivityIndicator, Alert, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { api, Account, Beneficiary } from "../api/client";
import { colors, styles as s } from "../theme";

export function BankingTransferScreen({ navigation }: any) {
  const [mode, setMode] = useState<"bank" | "upi">("bank");
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [beneficiaries, setBeneficiaries] = useState<Beneficiary[]>([]);
  const [fromAccountId, setFromAccountId] = useState<number>(0);
  const [beneficiaryId, setBeneficiaryId] = useState<number>(0);
  const [toUpiId, setToUpiId] = useState("");
  const [amount, setAmount] = useState("");
  const [reference, setReference] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all([api.accounts(), api.bankingBeneficiaries()]).then(([a, b]) => {
      setAccounts(a.accounts);
      setBeneficiaries(b.beneficiaries);
      if (a.accounts.length > 0) setFromAccountId(a.accounts[0].id);
    });
  }, []);

  const send = async () => {
    if (!amount || parseFloat(amount) <= 0) {
      setError("Enter a valid amount");
      return;
    }
    setError("");
    setBusy(true);
    try {
      if (mode === "bank") {
        if (!fromAccountId) { setError("Select source account"); return; }
        const body: any = { from_account_id: fromAccountId, amount: parseFloat(amount), reference };
        if (beneficiaryId) {
          body.beneficiary_id = beneficiaryId;
        } else {
          setError("Select or add a beneficiary");
          setBusy(false);
          return;
        }
        const result = await api.bankingTransfer(body);
        Alert.alert("Transfer Successful!", `₹${parseFloat(amount).toLocaleString("en-IN")} sent!\nUTR: ${result.utr}`, [{ text: "Done", onPress: () => navigation.navigate("BankingHome") }]);
      } else {
        if (!toUpiId) { setError("Enter UPI ID"); return; }
        const result = await api.bankingUpiPay({ to_upi_id: toUpiId, amount: parseFloat(amount), note });
        Alert.alert("UPI Payment Successful!", `₹${parseFloat(amount).toLocaleString("en-IN")} paid to ${toUpiId}\nRef: ${result.utr}`, [{ text: "Done", onPress: () => navigation.navigate("BankingHome") }]);
      }
    } catch (e: any) {
      setError(e.message || "Transfer failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScrollView style={s.screen}>
      <Pressable onPress={() => navigation.goBack()}>
        <Text style={{ color: colors.primary, marginBottom: 16, fontWeight: "600" }}>← Back</Text>
      </Pressable>
      <Text style={s.title}>Send Money</Text>

      {/* Mode Tabs */}
      <View style={{ flexDirection: "row", gap: 8, marginBottom: 20 }}>
        {(["bank", "upi"] as const).map((m) => (
          <Pressable key={m} onPress={() => setMode(m)} style={{
            flex: 1, padding: 12, borderRadius: 10, borderWidth: 2,
            borderColor: mode === m ? colors.primary : colors.line,
            backgroundColor: mode === m ? "#f0f0ff" : "#fff", alignItems: "center",
          }}>
            <Text style={{ fontWeight: "600", color: mode === m ? colors.primary : colors.muted }}>
              {m === "bank" ? "Bank Transfer" : "UPI Transfer"}
            </Text>
          </Pressable>
        ))}
      </View>

      {mode === "bank" ? (
        <>
          <Text style={{ fontWeight: "600", marginBottom: 8 }}>From Account</Text>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6, marginBottom: 16 }}>
            {accounts.map((acc) => (
              <Pressable key={acc.id} onPress={() => setFromAccountId(acc.id)} style={{
                padding: 10, borderRadius: 8, borderWidth: 2,
                borderColor: fromAccountId === acc.id ? colors.primary : colors.line,
                backgroundColor: fromAccountId === acc.id ? "#f0f0ff" : "#fff",
              }}>
                <Text style={{ fontSize: 13, fontWeight: "600" }}>{acc.name}</Text>
                <Text style={{ fontSize: 12, color: colors.muted }}>₹{acc.balance.toLocaleString("en-IN")}</Text>
              </Pressable>
            ))}
          </View>

          <Text style={{ fontWeight: "600", marginBottom: 8 }}>Beneficiary</Text>
          {beneficiaries.length > 0 && (
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6, marginBottom: 12 }}>
              {beneficiaries.map((b) => (
                <Pressable key={b.id} onPress={() => setBeneficiaryId(b.id)} style={{
                  padding: 10, borderRadius: 8, borderWidth: 2,
                  borderColor: beneficiaryId === b.id ? colors.primary : colors.line,
                  backgroundColor: beneficiaryId === b.id ? "#f0f0ff" : "#fff",
                }}>
                  <Text style={{ fontSize: 13, fontWeight: "600" }}>{b.name}</Text>
                  <Text style={{ fontSize: 11, color: colors.muted }}>{b.upi_id || `••••${b.account_number.slice(-4)}`}</Text>
                </Pressable>
              ))}
            </View>
          )}
        </>
      ) : (
        <>
          <Text style={{ fontWeight: "600", marginBottom: 8 }}>Pay to UPI ID</Text>
          <TextInput style={s.input} placeholder="example@upi" autoCapitalize="none" value={toUpiId} onChangeText={setToUpiId} />
          <Text style={{ color: colors.muted, fontSize: 12, marginBottom: 12 }}>e.g., name@icici, phone@paytm, number@ybl</Text>

          <Text style={{ fontWeight: "600", marginBottom: 8 }}>Note (optional)</Text>
          <TextInput style={s.input} placeholder="What's this for?" value={note} onChangeText={setNote} />
        </>
      )}

      <Text style={{ fontWeight: "600", marginBottom: 8 }}>Amount (₹)</Text>
      <TextInput style={[s.input, { fontSize: 24, fontWeight: "700", textAlign: "center", padding: 16 }]} placeholder="0.00" keyboardType="decimal-pad" value={amount} onChangeText={setAmount} />

      {mode === "bank" && (
        <>
          <Text style={{ fontWeight: "600", marginBottom: 8 }}>Reference (optional)</Text>
          <TextInput style={s.input} placeholder="e.g., Rent, Payment" value={reference} onChangeText={setReference} />
        </>
      )}

      {error ? <Text style={s.error}>{error}</Text> : null}
      <Pressable style={s.button} onPress={send} disabled={busy}>
        <Text style={s.buttonText}>{busy ? "Processing..." : mode === "bank" ? "Send Money 💸" : "Pay via UPI 📱"}</Text>
      </Pressable>

      {busy && <ActivityIndicator size="large" color={colors.primary} style={{ marginTop: 20 }} />}
    </ScrollView>
  );
}