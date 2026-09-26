import React, { useState, useEffect, useRef } from 'react';
import {
  StyleSheet,
  Text,
  View,
  FlatList,
  TouchableOpacity,
  ActivityIndicator,
  SafeAreaView,
  StatusBar,
  TextInput,
  Modal,
  Alert,
  KeyboardAvoidingView,
  Platform
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { FirebaseRecaptchaVerifierModal } from 'expo-firebase-recaptcha';
import { PhoneAuthProvider, signInWithCredential } from 'firebase/auth';
import { auth } from './firebase';

const BACKEND_URL = 'https://ipo-backend-fpjo.onrender.com';

export default function App() {
  const [ipos, setIpos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('ALL'); // ALL, MAINBOARD, SME
  const [searchQuery, setSearchQuery] = useState('');
  
  // Auth & OTP States
  const [userNumber, setUserNumber] = useState(null);
  const [authModalVisible, setAuthModalVisible] = useState(false);
  const [phoneNumber, setPhoneNumber] = useState('');
  const [verificationId, setVerificationId] = useState(null);
  const [otpCode, setOtpCode] = useState('');
  const [authLoading, setAuthLoading] = useState(false);
  const [resendTimer, setResendTimer] = useState(30);

  const recaptchaVerifier = useRef(null);

  useEffect(() => {
    loadUserSession();
    fetchIpos();
  }, []);

  useEffect(() => {
    let interval;
    if (verificationId && resendTimer > 0) {
      interval = setInterval(() => {
        setResendTimer((prev) => prev - 1);
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [verificationId, resendTimer]);

  const loadUserSession = async () => {
    try {
      const savedNumber = await AsyncStorage.getItem('user_phone_number');
      if (savedNumber) setUserNumber(savedNumber);
    } catch (e) {
      console.log('Error loading user session', e);
    }
  };

  const fetchIpos = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${BACKEND_URL}/api/ipos`);
      const data = await res.json();
      setIpos(Array.isArray(data) ? data : []);
    } catch (err) {
      console.log('Fetch error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSendOtp = async () => {
    if (!phoneNumber || phoneNumber.length < 10) {
      Alert.alert('Invalid Number', 'Kripya 10-digit mobile number enter karein.');
      return;
    }
    try {
      setAuthLoading(true);
      const fullPhone = phoneNumber.startsWith('+91') ? phoneNumber : `+91${phoneNumber}`;
      const phoneProvider = new PhoneAuthProvider(auth);
      const verId = await phoneProvider.verifyPhoneNumber(
        fullPhone,
        recaptchaVerifier.current
      );
      setVerificationId(verId);
      setResendTimer(30);
      Alert.alert('OTP Sent', `OTP ${fullPhone} par bhej diya gaya hai.`);
    } catch (err) {
      Alert.alert('Verification Failed', err.message || 'SMS send karne me dikkat aayi.');
    } finally {
      setAuthLoading(false);
    }
  };

  const handleVerifyOtp = async () => {
    if (!otpCode || otpCode.length < 6) {
      Alert.alert('Invalid OTP', 'Kripya 6-digit OTP code enter karein.');
      return;
    }
    try {
      setAuthLoading(true);
      const credential = PhoneAuthProvider.credential(verificationId, otpCode);
      await signInWithCredential(auth, credential);
      
      const fullPhone = phoneNumber.startsWith('+91') ? phoneNumber : `+91${phoneNumber}`;
      await AsyncStorage.setItem('user_phone_number', fullPhone);
      setUserNumber(fullPhone);
      setAuthModalVisible(false);
      setVerificationId(null);
      setOtpCode('');
      setPhoneNumber('');
      Alert.alert('Success', 'Mobile number successfully verify ho gaya!');
    } catch (err) {
      Alert.alert('Wrong OTP', 'Aapka dala gaya OTP galat ya expire ho chuka hai.');
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = async () => {
    Alert.alert('Logout', 'Kya aap logout karna chahte hain?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Logout',
        style: 'destructive',
        onPress: async () => {
          await AsyncStorage.removeItem('user_phone_number');
          setUserNumber(null);
        }
      }
    ]);
  };

  const filteredIpos = ipos.filter(item => {
    const matchesFilter =
      filter === 'ALL' ? true :
      filter === 'SME' ? (item.is_sme || item.category === 'SME') :
      (!item.is_sme && item.category !== 'SME');
    const matchesSearch = item.name ? item.name.toLowerCase().includes(searchQuery.toLowerCase()) : true;
    return matchesFilter && matchesSearch;
  });

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor="#0B0E14" />
      
      {/* Firebase reCAPTCHA Modal */}
      <FirebaseRecaptchaVerifierModal
        ref={recaptchaVerifier}
        firebaseConfig={auth.app.options}
        attemptInvisibleVerification={true}
      />

      {/* Top Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.headerTitle}>Apex IPO Tracker</Text>
          <Text style={styles.headerSubtitle}>Live GMP & Allotment Engine</Text>
        </View>

        {userNumber ? (
          <TouchableOpacity style={styles.userBadge} onPress={handleLogout}>
            <Text style={styles.userBadgeDot}>●</Text>
            <Text style={styles.userBadgeText}>{userNumber.slice(-4)}</Text>
          </TouchableOpacity>
        ) : (
          <TouchableOpacity
            style={styles.loginBtn}
            onPress={() => setAuthModalVisible(true)}
          >
            <Text style={styles.loginBtnText}>Verify Phone</Text>
          </TouchableOpacity>
        )}
      </View>

      {/* Search Input */}
      <View style={styles.searchContainer}>
        <TextInput
          style={styles.searchInput}
          placeholder="Search IPO by name..."
          placeholderTextColor="#64748B"
          value={searchQuery}
          onChangeText={setSearchQuery}
        />
      </View>

      {/* Filter Tabs */}
      <View style={styles.tabContainer}>
        {['ALL', 'MAINBOARD', 'SME'].map(t => (
          <TouchableOpacity
            key={t}
            style={[styles.tab, filter === t && styles.activeTab]}
            onPress={() => setFilter(t)}
          >
            <Text style={[styles.tabText, filter === t && styles.activeTabText]}>
              {t}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* List / Content */}
      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color="#38BDF8" />
          <Text style={styles.loadingText}>Syncing Live GMP Data...</Text>
        </View>
      ) : (
        <FlatList
          data={filteredIpos}
          keyExtractor={(item, index) => item.id || index.toString()}
          contentContainerStyle={styles.listContent}
          renderItem={({ item }) => (
            <View style={styles.card}>
              <View style={styles.cardHeader}>
                <Text style={styles.cardTitle}>{item.name}</Text>
                <View style={[styles.tag, item.is_sme ? styles.smeTag : styles.mainTag]}>
                  <Text style={styles.tagText}>{item.is_sme ? 'SME' : 'MAIN'}</Text>
                </View>
              </View>
              <View style={styles.row}>
                <View>
                  <Text style={styles.label}>Price Band</Text>
                  <Text style={styles.val}>₹{item.price || item.price_band || '--'}</Text>
                </View>
                <View>
                  <Text style={styles.label}>Est. Premium (GMP)</Text>
                  <Text style={styles.gmpVal}>+₹{item.gmp || 0} ({item.gain_percentage || 0}%)</Text>
                </View>
              </View>
            </View>
          )}
        />
      )}

      {/* OTP Authentication Modal */}
      <Modal
        visible={authModalVisible}
        transparent={true}
        animationType="slide"
        onRequestClose={() => setAuthModalVisible(false)}
      >
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={styles.modalOverlay}
        >
          <View style={styles.modalCard}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>
                {verificationId ? 'Enter 6-Digit OTP' : 'Verify Mobile Number'}
              </Text>
              <TouchableOpacity onPress={() => setAuthModalVisible(false)}>
                <Text style={styles.closeBtn}>✕</Text>
              </TouchableOpacity>
            </View>

            <Text style={styles.modalDesc}>
              {verificationId
                ? `SMS verification code has been sent to +91 ${phoneNumber}`
                : 'Free official SMS OTP verification powered by Google Firebase'}
            </Text>

            {!verificationId ? (
              <View style={styles.inputGroup}>
                <View style={styles.phoneInputRow}>
                  <Text style={styles.countryCode}>+91</Text>
                  <TextInput
                    style={styles.phoneInput}
                    placeholder="Enter 10 digit number"
                    placeholderTextColor="#64748B"
                    keyboardType="phone-pad"
                    maxLength={10}
                    value={phoneNumber}
                    onChangeText={setPhoneNumber}
                  />
                </View>
                <TouchableOpacity
                  style={styles.primaryBtn}
                  onPress={handleSendOtp}
                  disabled={authLoading}
                >
                  {authLoading ? (
                    <ActivityIndicator color="#0B0E14" />
                  ) : (
                    <Text style={styles.primaryBtnText}>Send OTP Code</Text>
                  )}
                </TouchableOpacity>
              </View>
            ) : (
              <View style={styles.inputGroup}>
                <TextInput
                  style={styles.otpInput}
                  placeholder="• • • • • •"
                  placeholderTextColor="#64748B"
                  keyboardType="number-pad"
                  maxLength={6}
                  value={otpCode}
                  onChangeText={setOtpCode}
                  textAlign="center"
                />

                <TouchableOpacity
                  style={styles.primaryBtn}
                  onPress={handleVerifyOtp}
                  disabled={authLoading}
                >
                  {authLoading ? (
                    <ActivityIndicator color="#0B0E14" />
                  ) : (
                    <Text style={styles.primaryBtnText}>Verify & Login</Text>
                  )}
                </TouchableOpacity>

                <View style={styles.resendRow}>
                  {resendTimer > 0 ? (
                    <Text style={styles.resendTimerText}>
                      Resend OTP in {resendTimer}s
                    </Text>
                  ) : (
                    <TouchableOpacity onPress={handleSendOtp} disabled={authLoading}>
                      <Text style={styles.resendBtnText}>Resend OTP Now</Text>
                    </TouchableOpacity>
                  )}
                </View>
              </View>
            )}
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0B0E14' },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#1E293B'
  },
  headerTitle: { fontSize: 20, fontWeight: '700', color: '#F8FAFC' },
  headerSubtitle: { fontSize: 11, color: '#94A3B8', marginTop: 2 },
  userBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#064E3B',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#10B981'
  },
  userBadgeDot: { color: '#10B981', fontSize: 12, marginRight: 6 },
  userBadgeText: { color: '#ECFDF5', fontSize: 12, fontWeight: '600' },
  loginBtn: {
    backgroundColor: '#38BDF8',
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 8
  },
  loginBtnText: { color: '#0B0E14', fontSize: 13, fontWeight: '700' },
  searchContainer: { paddingHorizontal: 16, marginTop: 12 },
  searchInput: {
    backgroundColor: '#1E293B',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    color: '#F8FAFC',
    fontSize: 14
  },
  tabContainer: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    marginVertical: 12,
    gap: 8
  },
  tab: {
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 6,
    backgroundColor: '#1E293B'
  },
  activeTab: { backgroundColor: '#38BDF8' },
  tabText: { color: '#94A3B8', fontSize: 12, fontWeight: '600' },
  activeTabText: { color: '#0B0E14', fontWeight: '700' },
  listContent: { paddingHorizontal: 16, paddingBottom: 24 },
  card: {
    backgroundColor: '#131B2E',
    borderRadius: 12,
    padding: 14,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: '#1E293B'
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10
  },
  cardTitle: { fontSize: 15, fontWeight: '700', color: '#F1F5F9', flex: 1 },
  tag: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 4 },
  mainTag: { backgroundColor: '#0369A1' },
  smeTag: { backgroundColor: '#7C3AED' },
  tagText: { color: '#FFF', fontSize: 10, fontWeight: '700' },
  row: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 4 },
  label: { fontSize: 11, color: '#64748B' },
  val: { fontSize: 13, fontWeight: '600', color: '#CBD5E1', marginTop: 2 },
  gmpVal: { fontSize: 14, fontWeight: '700', color: '#34D399', marginTop: 2 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  loadingText: { color: '#94A3B8', marginTop: 10, fontSize: 13 },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.75)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20
  },
  modalCard: {
    width: '100%',
    backgroundColor: '#131B2E',
    borderRadius: 16,
    padding: 20,
    borderWidth: 1,
    borderColor: '#334155'
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center'
  },
  modalTitle: { fontSize: 18, fontWeight: '700', color: '#F8FAFC' },
  closeBtn: { fontSize: 18, color: '#94A3B8' },
  modalDesc: { color: '#94A3B8', fontSize: 12, marginVertical: 12, lineHeight: 18 },
  inputGroup: { marginTop: 4 },
  phoneInputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1E293B',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#334155',
    marginBottom: 16
  },
  countryCode: {
    paddingHorizontal: 12,
    color: '#94A3B8',
    fontSize: 15,
    fontWeight: '600',
    borderRightWidth: 1,
    borderRightColor: '#334155'
  },
  phoneInput: {
    flex: 1,
    paddingHorizontal: 12,
    paddingVertical: 10,
    color: '#F8FAFC',
    fontSize: 16
  },
  otpInput: {
    backgroundColor: '#1E293B',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#38BDF8',
    paddingVertical: 12,
    color: '#38BDF8',
    fontSize: 22,
    letterSpacing: 8,
    marginBottom: 16
  },
  primaryBtn: {
    backgroundColor: '#38BDF8',
    borderRadius: 8,
    paddingVertical: 12,
    alignItems: 'center'
  },
  primaryBtnText: { color: '#0B0E14', fontSize: 14, fontWeight: '700' },
  resendRow: { alignItems: 'center', marginTop: 14 },
  resendTimerText: { color: '#64748B', fontSize: 12 },
  resendBtnText: { color: '#38BDF8', fontSize: 13, fontWeight: '600' }
});