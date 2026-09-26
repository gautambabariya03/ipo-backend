import React, { useState, useRef } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TextInput,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  SafeAreaView
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { FirebaseRecaptchaVerifierModal } from 'expo-firebase-recaptcha';
import { PhoneAuthProvider, signInWithCredential } from 'firebase/auth';
import { auth } from './firebase';

export default function LoginScreen({ onLoginSuccess }) {
  const [phoneNumber, setPhoneNumber] = useState('');
  const [verificationId, setVerificationId] = useState(null);
  const [otpCode, setOtpCode] = useState('');
  const [loading, setLoading] = useState(false);
  const recaptchaVerifier = useRef(null);

  const handleSendOtp = async () => {
    if (!phoneNumber || phoneNumber.length < 10) {
      Alert.alert('Galat Number', 'Kripya sahi 10-digit mobile number enter karein.');
      return;
    }
    try {
      setLoading(true);
      const fullPhone = phoneNumber.startsWith('+91') ? phoneNumber : `+91${phoneNumber}`;
      const phoneProvider = new PhoneAuthProvider(auth);
      const verId = await phoneProvider.verifyPhoneNumber(
        fullPhone,
        recaptchaVerifier.current
      );
      setVerificationId(verId);
      Alert.alert('OTP Sent', `Verification code ${fullPhone} par bhej diya gaya hai.`);
    } catch (err) {
      Alert.alert('SMS Error', err.message || 'OTP send karne mein issue aaya.');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtp = async () => {
    if (!otpCode || otpCode.length < 6) {
      Alert.alert('Galat OTP', 'Kripya 6-digit code enter karein.');
      return;
    }
    try {
      setLoading(true);
      const credential = PhoneAuthProvider.credential(verificationId, otpCode);
      await signInWithCredential(auth, credential);

      const fullPhone = phoneNumber.startsWith('+91') ? phoneNumber : `+91${phoneNumber}`;
      await AsyncStorage.setItem('user_phone_number', fullPhone);
      onLoginSuccess();
    } catch (err) {
      Alert.alert('Failed', 'OTP galat hai ya expire ho chuka hai.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <FirebaseRecaptchaVerifierModal
        ref={recaptchaVerifier}
        firebaseConfig={auth.app.options}
        attemptInvisibleVerification={true}
      />
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.inner}
      >
        <View style={styles.card}>
          <Text style={styles.title}>Apex IPO Tracker</Text>
          <Text style={styles.subtitle}>
            {verificationId
              ? 'Mobile par aaya 6-digit OTP code enter karein'
              : 'App open karne ke liye apna mobile number verify karein'}
          </Text>

          {!verificationId ? (
            <View>
              <View style={styles.inputContainer}>
                <Text style={styles.prefix}>+91</Text>
                <TextInput
                  style={styles.input}
                  placeholder="Mobile Number"
                  placeholderTextColor="#64748b"
                  keyboardType="phone-pad"
                  maxLength={10}
                  value={phoneNumber}
                  onChangeText={setPhoneNumber}
                />
              </View>

              <TouchableOpacity
                style={styles.btn}
                onPress={handleSendOtp}
                disabled={loading}
              >
                {loading ? (
                  <ActivityIndicator color="#0f172a" />
                ) : (
                  <Text style={styles.btnText}>Get OTP Code</Text>
                )}
              </TouchableOpacity>
            </View>
          ) : (
            <View>
              <TextInput
                style={styles.otpInput}
                placeholder="• • • • • •"
                placeholderTextColor="#64748b"
                keyboardType="number-pad"
                maxLength={6}
                value={otpCode}
                onChangeText={setOtpCode}
                textAlign="center"
              />

              <TouchableOpacity
                style={styles.btn}
                onPress={handleVerifyOtp}
                disabled={loading}
              >
                {loading ? (
                  <ActivityIndicator color="#0f172a" />
                ) : (
                  <Text style={styles.btnText}>Verify OTP & Continue</Text>
                )}
              </TouchableOpacity>
            </View>
          )}
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0b0f19', justifyContent: 'center' },
  inner: { flex: 1, justifyContent: 'center', paddingHorizontal: 24 },
  card: {
    backgroundColor: '#111827',
    padding: 24,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#1f2937'
  },
  title: { fontSize: 24, fontWeight: 'bold', color: '#f9fafb', marginBottom: 8 },
  subtitle: { fontSize: 13, color: '#9ca3af', marginBottom: 24 },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1f2937',
    borderRadius: 10,
    marginBottom: 20
  },
  prefix: { color: '#9ca3af', fontSize: 16, paddingLeft: 14, fontWeight: '600' },
  input: { flex: 1, padding: 14, color: '#fff', fontSize: 16 },
  otpInput: {
    backgroundColor: '#1f2937',
    borderRadius: 10,
    padding: 14,
    color: '#38bdf8',
    fontSize: 22,
    letterSpacing: 8,
    marginBottom: 20
  },
  btn: {
    backgroundColor: '#38bdf8',
    padding: 14,
    borderRadius: 10,
    alignItems: 'center'
  },
  btnText: { color: '#0f172a', fontWeight: 'bold', fontSize: 15 }
});