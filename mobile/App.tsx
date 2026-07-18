import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { StatusBar } from "expo-status-bar";
import React from "react";
import { ActivityIndicator, Text, View } from "react-native";

import { AuthProvider, useAuth } from "./src/context/AuthContext";
import { AccountsScreen } from "./src/screens/AccountsScreen";
import { AuthScreen } from "./src/screens/AuthScreen";
import { BankingBillsScreen } from "./src/screens/BankingBillsScreen";
import { BankingConnectScreen } from "./src/screens/BankingConnectScreen";
import { BankingHomeScreen } from "./src/screens/BankingHomeScreen";
import { BankingHistoryScreen } from "./src/screens/BankingHistoryScreen";
import { BankingTransferScreen } from "./src/screens/BankingTransferScreen";
import { BudgetsScreen } from "./src/screens/BudgetsScreen";
import { DashboardScreen } from "./src/screens/DashboardScreen";
import { SettingsScreen } from "./src/screens/SettingsScreen";
import { TransactionsScreen } from "./src/screens/TransactionsScreen";

const Stack = createNativeStackNavigator();
const BankingStack = createNativeStackNavigator();
const Tabs = createBottomTabNavigator();

function BankingStackNavigator() {
  return (
    <BankingStack.Navigator screenOptions={{ headerShown: false }}>
      <BankingStack.Screen name="BankingHome" component={BankingHomeScreen} />
      <BankingStack.Screen name="BankingConnect" component={BankingConnectScreen} />
      <BankingStack.Screen name="BankingTransfer" component={BankingTransferScreen} />
      <BankingStack.Screen name="BankingBills" component={BankingBillsScreen} />
      <BankingStack.Screen name="BankingHistory" component={BankingHistoryScreen} />
    </BankingStack.Navigator>
  );
}

function MainTabs() {
  return (
    <Tabs.Navigator screenOptions={{ headerShown: false }}>
      <Tabs.Screen name="Dashboard" component={DashboardScreen} />
      <Tabs.Screen name="Banking" component={BankingStackNavigator} />
      <Tabs.Screen name="Transactions" component={TransactionsScreen} />
      <Tabs.Screen name="Accounts" component={AccountsScreen} />
      <Tabs.Screen name="Settings" component={SettingsScreen} />
    </Tabs.Navigator>
  );
}

function RootNavigator() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
        <ActivityIndicator size="large" color="#123c69" />
      </View>
    );
  }

  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      {user ? (
        <Stack.Screen name="Main" component={MainTabs} />
      ) : (
        <Stack.Screen name="Auth" component={AuthScreen} />
      )}
    </Stack.Navigator>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <NavigationContainer>
        <StatusBar style="dark" />
        <RootNavigator />
      </NavigationContainer>
    </AuthProvider>
  );
}
