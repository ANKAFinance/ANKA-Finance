import React, { useState } from "react";
import { Pressable, ScrollView, Text, TextInput, View } from "react-native";

import { useAuth } from "../context/AuthContext";
import { styles } from "../theme";

export function AuthScreen() {
  const { signIn, signUp } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setError("");
    setBusy(true);
    try {
      if (mode === "register") {
        await signUp(name, email, password, "USD");
      } else {
        await signIn(email, password);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScrollView contentContainerStyle={[styles.screen, { justifyContent: "center" }]}>
      <Text style={styles.title}>ANKA Finance</Text>
      <Text style={styles.subtitle}>Take control of your financial future</Text>

      {mode === "register" && (
        <TextInput style={styles.input} placeholder="Name" value={name} onChangeText={setName} />
      )}
      <TextInput
        style={styles.input}
        placeholder="Email"
        autoCapitalize="none"
        keyboardType="email-address"
        value={email}
        onChangeText={setEmail}
      />
      <TextInput
        style={styles.input}
        placeholder="Password (8+ characters)"
        secureTextEntry
        value={password}
        onChangeText={setPassword}
      />

      {error ? <Text style={styles.error}>{error}</Text> : null}

      <Pressable style={styles.button} onPress={submit} disabled={busy}>
        <Text style={styles.buttonText}>{busy ? "Please wait..." : mode === "register" ? "Create account" : "Sign in"}</Text>
      </Pressable>

      <Pressable style={styles.secondaryButton} onPress={() => setMode(mode === "login" ? "register" : "login")}>
        <Text>{mode === "login" ? "Need an account? Register" : "Already registered? Sign in"}</Text>
      </Pressable>
    </ScrollView>
  );
}
