import React, { useState, useEffect, useRef } from 'react';
import {
  StyleSheet,
  Text,
  View,
  FlatList,
  TouchableOpacity,
  SafeAreaView,
  StatusBar,
  ActivityIndicator,
  RefreshControl,
  Modal,
  TextInput,
  ScrollView,
  Share,
  Alert,
  Linking,
  Animated,
  Image,
  Platform,
  BackHandler
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Ionicons } from '@expo/vector-icons';
import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import Constants from 'expo-constants';

// App band / background / killed — kisi bhi state me notification aaye toh phone ke
// notification-shade / lock-screen pe dikhe (WhatsApp jaisa)
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
  }),
});

const BASE_URL = 'https://ipo-backend-fpjo.onrender.com';
const API_URL = `${BASE_URL}/api/ipos/live`;
const ALLOTMENT_API = `${BASE_URL}/api/allotment/check-batch`;
const MAX_SCAN_ROUNDS = 3; // captcha/OCR atke toh ek account ko itni baar dobara try karo

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
const AVATAR_COLORS = ['#7C3AED', '#2563EB', '#D97706', '#DB2777', '#059669', '#DC2626', '#0891B2', '#EA580C'];
function avatarColor(name) {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

function initials(name) {
  const parts = (name || '?').replace(/[^A-Za-z0-9 ]/g, ' ').trim().split(/\s+/);
  return ((parts[0] || '?')[0] + (parts.length > 1 ? parts[1][0] : '')).toUpperCase();
}

// Company logo: naam se domain guess karke favicon try karta hai; load fail ho toh
// initials-avatar. NOTE: best-effort — guess hamesha sahi nahi hoga.
function guessDomain(name) {
  let n = name.replace(/\(.*?\)/g, '');
  n = n.replace(/\b(Ltd\.?|Limited|IPO|SME|BSE|NSE|India)\b/gi, '');
  n = n.replace(/[^a-zA-Z0-9\s]/g, '').trim().toLowerCase();
  const first = n.split(/\s+/)[0];
  return first && first.length > 2 ? `${first}.com` : null;
}

function CompanyLogo({ name, size = 52 }) {
  const [failed, setFailed] = useState(false);
  const domain = guessDomain(name);
  const radius = size / 2;
  if (failed || !domain) {
    return (
      <View style={{ width: size, height: size, borderRadius: radius, backgroundColor: avatarColor(name), justifyContent: 'center', alignItems: 'center' }}>
        <Text style={{ color: '#fff', fontSize: size * 0.36, fontWeight: '800' }}>{initials(name)}</Text>
      </View>
    );
  }
  return (
    <View style={{ width: size, height: size, borderRadius: radius, backgroundColor: '#fff', justifyContent: 'center', alignItems: 'center', overflow: 'hidden' }}>
      <Image
        source={{ uri: `https://www.google.com/s2/favicons?sz=128&domain=${domain}` }}
        style={{ width: size * 0.62, height: size * 0.62 }}
        resizeMode="contain"
        onError={() => setFailed(true)}
      />
    </View>
  );
}

function Avatar({ name, size = 44 }) {
  return (
    <View style={{ width: size, height: size, borderRadius: size / 2, backgroundColor: avatarColor(name), justifyContent: 'center', alignItems: 'center' }}>
      <Text style={{ color: '#fff', fontSize: size * 0.38, fontWeight: '800' }}>{initials(name)}</Text>
    </View>
  );
}

const fmtMoney = (v) => (typeof v === 'number' ? v.toLocaleString('en-IN') : v);

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------
export default function App() {
  // Data
  const [ipos, setIpos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  // Navigation / filters
  const [activeTab, setActiveTab] = useState('IPO'); // IPO | Account | Allotment
  const [statusFilter, setStatusFilter] = useState('OPEN');
  const [categoryFilter, setCategoryFilter] = useState('ALL');
  const [isDarkMode, setIsDarkMode] = useState(true);
  const [blinkOn, setBlinkOn] = useState(true);

  // Vault
  const [accounts, setAccounts] = useState([]);
  const [accountModalOpen, setAccountModalOpen] = useState(false);
  const [newName, setNewName] = useState('');
  const [newPan, setNewPan] = useState('');
  const [newAccountType, setNewAccountType] = useState('CDSL');
  const [newClientId, setNewClientId] = useState('');
  const [newUpiId, setNewUpiId] = useState('');

  // Allotment
  const [selectedAllotmentIpo, setSelectedAllotmentIpo] = useState(null);
  const [ipoPickerOpen, setIpoPickerOpen] = useState(false);
  const [checkingProgress, setCheckingProgress] = useState(null);
  const [allotmentResults, setAllotmentResults] = useState({});

  // Notifications / push
  const [notifications, setNotifications] = useState([]);
  const [notifModalOpen, setNotifModalOpen] = useState(false);
  const [unreadNotifCount, setUnreadNotifCount] = useState(0);
  const [pushStatus, setPushStatus] = useState({ ok: null, msg: 'Check ho raha hai...' });

  // Search / settings
  const [searchModalOpen, setSearchModalOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [highlightedIpoId, setHighlightedIpoId] = useState(null);
  const [settingsModalOpen, setSettingsModalOpen] = useState(false);

  // Card reverse (flip) popup
  const [backItem, setBackItem] = useState(null);
  const [detailCache, setDetailCache] = useState({});
  const flipAnim = useRef(new Animated.Value(0)).current;

  // App-open splash (user ki image) — native splash ke baad ~2 sec
  const [showIntro, setShowIntro] = useState(true);
  const introOpacity = useRef(new Animated.Value(1)).current;
  useEffect(() => {
    Animated.sequence([
      Animated.delay(1500),
      Animated.timing(introOpacity, { toValue: 0, duration: 450, useNativeDriver: true }),
    ]).start(() => setShowIntro(false));
  }, []);

  // ---------------- effects ----------------
  useEffect(() => {
    const timer = setInterval(() => setBlinkOn(prev => !prev), 700);
    loadSavedAccounts();
    loadSavedTheme();
    fetchLiveIPOs();
    fetchNotifications();
    registerForPushNotifications();
    return () => clearInterval(timer);
  }, []);

  // Har 30 sec me list + notifications khud refresh
  useEffect(() => {
    const pollTimer = setInterval(() => {
      fetchLiveIPOs();
      fetchNotifications();
    }, 30000);
    return () => clearInterval(pollTimer);
  }, []);

  // Android back button: pehle khule popup band karo, phir IPO tab par wapas
  useEffect(() => {
    const onBackPress = () => {
      if (backItem) { closeBack(); return true; }
      if (searchModalOpen) { setSearchModalOpen(false); return true; }
      if (notifModalOpen) { setNotifModalOpen(false); return true; }
      if (settingsModalOpen) { setSettingsModalOpen(false); return true; }
      if (accountModalOpen) { setAccountModalOpen(false); return true; }
      if (ipoPickerOpen) { setIpoPickerOpen(false); return true; }
      if (activeTab !== 'IPO') { setActiveTab('IPO'); return true; }
      return false;
    };
    const sub = BackHandler.addEventListener('hardwareBackPress', onBackPress);
    return () => sub.remove();
  }, [activeTab, backItem, searchModalOpen, notifModalOpen, settingsModalOpen, accountModalOpen, ipoPickerOpen]);

  // ---------------- data ----------------
  const fetchLiveIPOs = async () => {
    try {
      const resp = await fetch(API_URL);
      const data = await resp.json();
      setIpos(data);
      setFetchError(null);
      setSelectedAllotmentIpo(prev => {
        if (prev) return data.find(x => x.id === prev.id) || prev; // fresh data (registrar_url etc.)
        return data.find(x => x.status === 'CLOSED' && x.allotment_declared) || null;
      });
    } catch (e) {
      console.log('Fetch Error:', e);
      setFetchError('server_unreachable');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const fetchNotifications = async () => {
    try {
      const resp = await fetch(`${BASE_URL}/api/notifications`);
      const data = await resp.json();
      setNotifications(data);
      const lastSeen = await AsyncStorage.getItem('@last_seen_notif_time');
      const unread = lastSeen ? data.filter(n => n.time > lastSeen).length : data.length;
      setUnreadNotifCount(unread);
    } catch (e) {
      console.log('Notification Fetch Error:', e);
    }
  };

  const openNotifications = async () => {
    setNotifModalOpen(true);
    setUnreadNotifCount(0);
    if (notifications.length > 0) {
      await AsyncStorage.setItem('@last_seen_notif_time', notifications[0].time);
    }
  };

  // Phone ke home-screen / notification-shade wale (real) push notifications
  const registerForPushNotifications = async () => {
    try {
      if (!Device.isDevice) {
        setPushStatus({ ok: false, msg: 'Asli phone chahiye (emulator me push nahi chalta)' });
        return;
      }
      if (Constants.executionEnvironment === 'storeClient' || Constants.appOwnership === 'expo') {
        setPushStatus({ ok: false, msg: 'Expo Go me push nahi chalta — development/production build (eas build) chahiye' });
        return;
      }
      if (Platform.OS === 'android') {
        await Notifications.setNotificationChannelAsync('default', {
          name: 'IPO Alerts',
          importance: Notifications.AndroidImportance.MAX,
          vibrationPattern: [0, 250, 250, 250],
          lightColor: '#A43FE3',
        });
      }
      const existing = await Notifications.getPermissionsAsync();
      let finalStatus = existing.status;
      if (finalStatus !== 'granted') {
        const requested = await Notifications.requestPermissionsAsync();
        finalStatus = requested.status;
      }
      if (finalStatus !== 'granted') {
        setPushStatus({ ok: false, msg: 'Notification permission band hai — phone Settings → Apps → IPO → Notifications ON karo' });
        return;
      }
      const projectId = Constants.expoConfig?.extra?.eas?.projectId ?? Constants.easConfig?.projectId;
      if (!projectId) {
        setPushStatus({ ok: false, msg: 'EAS projectId nahi mila (app.json extra.eas.projectId)' });
        return;
      }
      const tokenResponse = await Notifications.getExpoPushTokenAsync({ projectId });
      const resp = await fetch(`${BASE_URL}/api/register-push-token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: tokenResponse.data }),
      });
      if (!resp.ok) throw new Error(`Server ne token reject kiya (${resp.status})`);
      setPushStatus({ ok: true, msg: 'Push ON — is phone ka token server par registered hai' });
    } catch (e) {
      const m = String(e?.message || e);
      const fcm = /firebase|fcm|google-services|firebaseapp/i.test(m);
      setPushStatus({
        ok: false,
        msg: fcm
          ? 'Android push ke liye Firebase (FCM) setup baaki hai — neeche guide dekho. (' + m.slice(0, 80) + ')'
          : m.slice(0, 180),
      });
    }
  };

  const sendTestPush = async () => {
    try {
      const resp = await fetch(`${BASE_URL}/api/test-push`);
      const data = await resp.json();
      Alert.alert(
        'Test push',
        data.devices === 0
          ? 'Server par abhi koi device registered nahi hai. Pehle "Push ON" status aane do.'
          : `Bheja gaya: ${data.devices} device(s)\n${data.summary || ''}\n\nPhone ke notification-shade me 5-10 sec me aana chahiye (app band karke dekho).`
      );
    } catch (e) {
      Alert.alert('Test push', 'Server tak pahunch nahi paaye: ' + String(e?.message || e));
    }
  };

  // ---------------- storage ----------------
  const loadSavedTheme = async () => {
    try {
      const savedTheme = await AsyncStorage.getItem('@app_theme');
      if (savedTheme !== null) setIsDarkMode(savedTheme === 'dark');
    } catch (e) {
      console.log('Theme load error:', e);
    }
  };

  const setThemeMode = async (mode) => {
    const isDark = mode === 'dark';
    setIsDarkMode(isDark);
    await AsyncStorage.setItem('@app_theme', isDark ? 'dark' : 'light');
  };

  const loadSavedAccounts = async () => {
    try {
      const data = await AsyncStorage.getItem('@family_accounts');
      if (data) {
        setAccounts(JSON.parse(data));
      } else {
        const defaults = [
          { id: '1', name: 'GAUTAM BABARIYA', pan: 'GSXPB6123C' },
          { id: '2', name: 'RAJNI SONDARVA', pan: 'XXXXXXX53D' },
          { id: '3', name: 'POOJA BABARIYA', pan: 'IVVPB3768J' },
          { id: '4', name: 'ABHI BABARIYA', pan: 'FYMPB2800N' },
          { id: '5', name: 'GAUTAM CHAUHAN', pan: 'FSDPP6640D' },
          { id: '6', name: 'ALPABEN BABARIYA', pan: 'IZZPB8925F' }
        ];
        setAccounts(defaults);
        await AsyncStorage.setItem('@family_accounts', JSON.stringify(defaults));
      }
    } catch (e) {
      console.log('Accounts Load Error:', e);
    }
  };

  const saveAccount = async () => {
    if (!newName.trim() || !newPan.trim()) {
      Alert.alert('Required', 'Please enter Name and PAN Number');
      return;
    }
    const updated = [
      ...accounts,
      {
        id: Date.now().toString(),
        name: newName.toUpperCase().trim(),
        pan: newPan.toUpperCase().trim(),
        accountType: newAccountType,
        clientId: newClientId.trim(),
        upiId: newUpiId.trim(),
      }
    ];
    setAccounts(updated);
    await AsyncStorage.setItem('@family_accounts', JSON.stringify(updated));
    setNewName('');
    setNewPan('');
    setNewAccountType('CDSL');
    setNewClientId('');
    setNewUpiId('');
    setAccountModalOpen(false);
  };

  const deleteAccount = (acc) => {
    Alert.alert('Delete account?', `${acc.name} (${acc.pan}) Vault se hata dein?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          const updated = accounts.filter(x => x.id !== acc.id);
          setAccounts(updated);
          await AsyncStorage.setItem('@family_accounts', JSON.stringify(updated));
        },
      },
    ]);
  };

  // ---------------- card reverse (flip) ----------------
  const loadDetail = async (item) => {
    if (detailCache[item.id]?.loaded) return;
    try {
      const resp = await fetch(`${BASE_URL}/api/ipos/detail/${item.id}`);
      const d = await resp.json();
      setDetailCache(prev => ({
        ...prev,
        [item.id]: {
          loaded: true,
          registrar: d?.registrar?.name || null,
          registrar_url: d?.registrar_url || null,
          lead_managers: (d?.lead_managers && d.lead_managers.length > 0) ? d.lead_managers.join(', ') : null,
        },
      }));
    } catch (e) {
      setDetailCache(prev => ({ ...prev, [item.id]: { loaded: true, registrar: null, registrar_url: null, lead_managers: null } }));
    }
  };

  const openBack = (item) => {
    setBackItem(item);
    flipAnim.setValue(0);
    Animated.timing(flipAnim, { toValue: 1, duration: 450, useNativeDriver: true }).start();
    loadDetail(item);
  };

  const closeBack = () => {
    Animated.timing(flipAnim, { toValue: 0, duration: 250, useNativeDriver: true }).start(() => setBackItem(null));
  };

  // ---------------- registrar redirect ----------------
  // Hamesha IPO ke ASLI registrar ki site (BSE/NSE ki generic page kabhi nahi)
  const resolveRegistrarUrl = async (ipo) => {
    if (!ipo) return null;
    if (ipo.registrar_url) return ipo.registrar_url;
    if (detailCache[ipo.id]?.registrar_url) return detailCache[ipo.id].registrar_url;
    try {
      const resp = await fetch(`${BASE_URL}/api/ipos/detail/${ipo.id}`);
      const d = await resp.json();
      setDetailCache(prev => ({
        ...prev,
        [ipo.id]: {
          loaded: true,
          registrar: d?.registrar?.name || null,
          registrar_url: d?.registrar_url || null,
          lead_managers: (d?.lead_managers && d.lead_managers.length > 0) ? d.lead_managers.join(', ') : null,
        },
      }));
      return d?.registrar_url || null;
    } catch (e) {
      return null;
    }
  };

  const openRegistrarSite = async (ipo) => {
    const url = await resolveRegistrarUrl(ipo);
    if (url) {
      Linking.openURL(url);
    } else {
      Alert.alert(
        'Registrar abhi pata nahi',
        'Is IPO ka registrar abhi source me nahi mila. Thodi der baad dobara try karo (app khud 3 min me dhoondhta rehta hai).'
      );
    }
  };

  // ---------------- allotment scan ----------------
  // Har account ke liye alag request: server registrar site par OCR se captcha solve karke
  // check karta hai. Captcha/OCR atke toh app khud dobara (max MAX_SCAN_ROUNDS) try karta hai.
  const checkOneAccount = async (acc, registrarUrl) => {
    try {
      const resp = await fetch(ALLOTMENT_API, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ipo_name: selectedAllotmentIpo.name,
          lot_size: selectedAllotmentIpo.lot_size || 50,
          accounts: [{ id: acc.id, name: acc.name, pan: acc.pan }],
          registrar_url: registrarUrl || null,
        }),
      });
      const data = await resp.json();
      if (data.success && data.results && data.results[acc.id]) return data.results[acc.id];
      return { status: 'UNVERIFIED', shares: 'Registrar response nahi mila', retryable: true };
    } catch (e) {
      console.log('Allotment Engine Error:', e);
      return { status: 'UNVERIFIED', shares: 'Server tak pahunch nahi paaye', retryable: false };
    }
  };

  const checkAccountWithRetry = async (acc, idx, total, registrarUrl) => {
    let res = null;
    for (let round = 1; round <= MAX_SCAN_ROUNDS; round++) {
      setCheckingProgress(`Checking ${idx + 1} of ${total} — ${acc.name}${round > 1 ? ` (retry ${round - 1})` : ''}`);
      res = await checkOneAccount(acc, registrarUrl);
      if (res.status !== 'UNVERIFIED' || !res.retryable) break;
    }
    return res;
  };

  const startBatchCheck = async () => {
    if (accounts.length === 0) {
      Alert.alert('No Accounts', 'Pehle Vault me kam se kam ek PAN add karo');
      return;
    }
    if (!selectedAllotmentIpo) {
      Alert.alert('Select IPO', 'Pehle target IPO select karo');
      return;
    }
    setAllotmentResults({});
    setCheckingProgress('Registrar dhoondh rahe hain...');
    const registrarUrl = await resolveRegistrarUrl(selectedAllotmentIpo);
    for (let i = 0; i < accounts.length; i++) {
      const acc = accounts[i];
      const res = await checkAccountWithRetry(acc, i, accounts.length, registrarUrl);
      setAllotmentResults(prev => ({ ...prev, [acc.id]: res }));
    }
    setCheckingProgress(null);
  };

  const shareStatus = async (item, res) => {
    try {
      await Share.share({
        message: `IPO Allotment Update:\nIPO: ${selectedAllotmentIpo?.name}\nAccount: ${item.name}\nStatus: ${res?.shares || 'Pending'}`
      });
    } catch (e) {
      console.log('Share Error:', e);
    }
  };

  // ---------------- derived ----------------
  const displayList = ipos
    .filter(item => {
      const matchStatus = item.status === statusFilter;
      const matchCategory = categoryFilter === 'ALL' || item.category === categoryFilter;
      return matchStatus && matchCategory;
    })
    .sort((a, b) => {
      if (highlightedIpoId) {
        if (a.id === highlightedIpoId) return -1;
        if (b.id === highlightedIpoId) return 1;
      }
      if (statusFilter !== 'CLOSED') return 0;
      return (b.allotment_declared ? 1 : 0) - (a.allotment_declared ? 1 : 0);
    });

  const allotmentEligibleIpos = ipos.filter(item => item.status === 'CLOSED' && item.allotment_declared);

  const searchResults = searchQuery.trim()
    ? ipos.filter(item => item.name.toLowerCase().includes(searchQuery.trim().toLowerCase()))
    : [];

  const theme = isDarkMode
    ? {
        bg: '#0F1118', headerBg: '#0F1118', cardBg: '#1A1C2B', innerBox: '#222439', border: '#2A2C42',
        textMain: '#F4F4FA', textSub: '#9A9CB5', accent: '#A43FE3', accentText: '#B66BFF',
        accentSoft: 'rgba(164,63,227,0.14)', tickerBorder: 'rgba(164,63,227,0.85)', blueBorder: '#2F4A8A',
        good: '#34D399', bad: '#F87171', modalBg: '#171827', backdrop: 'rgba(5,5,12,0.80)',
      }
    : {
        bg: '#F4F3FA', headerBg: '#FFFFFF', cardBg: '#FFFFFF', innerBox: '#F0EEF8', border: '#E3DFF0',
        textMain: '#17142A', textSub: '#6B6884', accent: '#8E2FD0', accentText: '#8E2FD0',
        accentSoft: 'rgba(142,47,208,0.10)', tickerBorder: 'rgba(142,47,208,0.7)', blueBorder: '#9DB4E8',
        good: '#059669', bad: '#DC2626', modalBg: '#FFFFFF', backdrop: 'rgba(20,10,40,0.55)',
      };

  const liveBarColor = activeTab !== 'IPO'
    ? theme.accent
    : statusFilter === 'OPEN' ? '#22E06B' : statusFilter === 'UPCOMING' ? theme.accent : theme.textSub;

  // ---------------------------------------------------------------------------
  // Render helpers
  // ---------------------------------------------------------------------------
  const renderIpoCard = ({ item }) => {
    const hasGmp = item.gmp > 0;
    const isClosed = item.status === 'CLOSED';
    const isMain = item.category !== 'SME';
    const priceColor = (v) => {
      const s = String(v || '');
      if (!s || s.includes('--')) return theme.textMain;
      return s.includes('-') ? theme.bad : theme.good;
    };
    const registrarKnown = item.registrar && item.registrar !== 'Not available yet';

    return (
      <View style={[styles.card, { backgroundColor: theme.cardBg, borderColor: theme.border }]}>
        <View style={styles.cardTop}>
          <CompanyLogo name={item.name} size={54} />
          <View style={styles.cardTitleCol}>
            <View style={[styles.catBadge, { backgroundColor: isMain ? '#2A4A82' : '#D9801C' }]}>
              <Text style={styles.catBadgeText}>{isMain ? 'MAINBOARD' : 'SME'}</Text>
            </View>
            <Text style={[styles.cardName, { color: theme.textMain }]} numberOfLines={2}>{item.name}</Text>
            <View style={styles.dateRow}>
              <Ionicons name="calendar-outline" size={14} color={theme.textSub} />
              <Text style={[styles.dateText, { color: theme.textMain }]}>{item.date_range}</Text>
            </View>
          </View>
          <TouchableOpacity style={styles.flipBtn} onPress={() => openBack(item)} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
            <Ionicons name="sync-outline" size={19} color={theme.textSub} />
          </TouchableOpacity>
        </View>

        {isClosed ? (
          <>
            <View style={[styles.perfBox, { borderColor: theme.border }]}>
              <View style={[styles.perfCol, { borderRightWidth: 1, borderRightColor: theme.border }]}>
                <Text style={[styles.perfLabel, { color: theme.textSub }]}>LISTING PRICE</Text>
                <Text style={[styles.perfValue, { color: priceColor(item.listing_price) }]} numberOfLines={1} adjustsFontSizeToFit>
                  {item.listing_price}
                </Text>
              </View>
              <View style={styles.perfCol}>
                <Text style={[styles.perfLabel, { color: theme.textSub }]}>CURRENT CMP</Text>
                <Text style={[styles.perfValue, { color: priceColor(item.current_price) }]} numberOfLines={1} adjustsFontSizeToFit>
                  {item.current_price}
                </Text>
              </View>
            </View>

            <View style={styles.footerRow}>
              <Text style={[styles.footerTxt, { color: theme.textSub }]}>
                Allotment: <Text style={[styles.footerVal, { color: theme.textMain }]}>{item.allotment_date}</Text>
              </Text>
              <Text style={[styles.footerTxt, { color: theme.textSub }]}>
                Listing: <Text style={[styles.footerVal, { color: theme.textMain }]}>{item.listing_date}</Text>
              </Text>
            </View>

            <TouchableOpacity
              style={[styles.primaryBtn, { backgroundColor: theme.accent }]}
              activeOpacity={0.85}
              onPress={() => openRegistrarSite(item)}
            >
              <Text style={styles.primaryBtnText}>CHECK ALLOTMENT</Text>
            </TouchableOpacity>
            {registrarKnown && (
              <Text style={[styles.registrarHint, { color: theme.textSub }]}>Registrar: {item.registrar}</Text>
            )}
          </>
        ) : (
          <>
            <View style={[styles.ticker, { borderColor: theme.tickerBorder }]}>
              <View style={{ flex: 1 }}>
                <View style={styles.tickerLabelRow}>
                  <View style={[styles.tickerDot, { backgroundColor: theme.accent, opacity: blinkOn ? 1 : 0.4 }]} />
                  <Text style={[styles.tickerLabel, { color: theme.textMain }]}>LIVE GMP TICKER</Text>
                </View>
                <Text style={[styles.tickerUpdated, { color: theme.textSub }]}>Updated: {item.last_heard}</Text>
              </View>
              <View style={{ alignItems: 'flex-end' }}>
                <Text style={[styles.tickerValue, { color: theme.textMain }]}>{hasGmp ? `+₹${item.gmp}` : '--'}</Text>
                <Text style={[styles.tickerGain, { color: theme.accentText }]}>
                  {hasGmp ? `${item.gmp_percentage}% EST. GAIN` : 'NOT DECLARED'}
                </Text>
              </View>
            </View>

            <View style={styles.specRow}>
              <View style={[styles.specCol, { borderRightWidth: 1, borderRightColor: theme.border }]}>
                <Text style={[styles.specLabel, { color: theme.textSub }]}>ISSUE PRICE:</Text>
                <Text style={[styles.specValue, { color: theme.textMain }]}>{item.price}</Text>
              </View>
              <View style={[styles.specCol, { borderRightWidth: 1, borderRightColor: theme.border }]}>
                <Text style={[styles.specLabel, { color: theme.textSub }]}>LOT SIZE:</Text>
                <Text style={[styles.specValue, { color: theme.textMain }]}>{item.lot_size} sh</Text>
              </View>
              <View style={styles.specCol}>
                <Text style={[styles.specLabel, { color: theme.textSub }]}>ISSUE SIZE:</Text>
                <Text style={[styles.specValue, { color: theme.textMain }]}>{item.issue_size}</Text>
              </View>
            </View>

            <View style={styles.profitRow}>
              <View style={[styles.profitBox, { backgroundColor: theme.innerBox, borderColor: theme.blueBorder }]}>
                <Text style={[styles.profitLabel, { color: theme.textSub }]}>EST. RETAIL PROFIT:</Text>
                <Text style={[styles.profitValue, { color: theme.accentText }]}>
                  {hasGmp && item.retail_profit != null ? `₹${fmtMoney(item.retail_profit)}` : '--'}
                </Text>
              </View>
              <View style={[styles.profitBox, { backgroundColor: theme.innerBox, borderColor: theme.blueBorder }]}>
                <Text style={[styles.profitLabel, { color: theme.textSub }]}>EST. HNI PROFIT:</Text>
                <Text style={[styles.profitValue, { color: theme.accentText }]}>
                  {hasGmp && item.hni_profit != null ? `₹${fmtMoney(item.hni_profit)}` : '--'}
                </Text>
              </View>
            </View>

            <View style={styles.footerRow}>
              <Text style={[styles.footerTxt, { color: theme.textSub }]}>
                Allotment: <Text style={[styles.footerVal, { color: theme.textMain }]}>{item.allotment_date}</Text>
              </Text>
              <Text style={[styles.footerTxt, { color: theme.textSub }]}>
                Listing: <Text style={[styles.footerVal, { color: theme.textMain }]}>{item.listing_date}</Text>
              </Text>
              {hasGmp && (
                <Text style={[styles.footerTxt, { color: theme.textSub }]}>
                  OMP: <Text style={[styles.footerVal, { color: theme.textMain }]}>{item.gmp}</Text>
                </Text>
              )}
            </View>
          </>
        )}
      </View>
    );
  };

  const pillFor = (res) => {
    if (!res) return { bg: theme.innerBox, color: theme.textSub, label: 'PENDING', icon: null };
    if (res.status === 'ALLOTTED') return { bg: '#1F8A4C', color: '#fff', label: 'ALLOTTED', icon: 'checkmark' };
    if (res.status === 'NON_ALLOTTEE') return { bg: '#B3261E', color: '#fff', label: 'NOT ALLOTTED', icon: null };
    if (res.status === 'NOT_APPLIED') return { bg: '#3A3C55', color: '#fff', label: 'NOT APPLIED', icon: null };
    return { bg: '#C27A0E', color: '#fff', label: 'COULD NOT VERIFY', icon: null };
  };

  const renderAccountResult = ({ item }) => {
    const res = allotmentResults[item.id];
    const pill = pillFor(res);
    return (
      <View style={[styles.resultCard, { backgroundColor: theme.cardBg, borderColor: theme.border }]}>
        <Avatar name={item.name} size={46} />
        <View style={{ flex: 1, marginLeft: 12 }}>
          <Text style={[styles.resultName, { color: theme.textMain }]} numberOfLines={1}>{item.name}</Text>
          <View style={[styles.statusPill, { backgroundColor: pill.bg }]}>
            <Text style={[styles.statusPillText, { color: pill.color }]}>{pill.label}</Text>
            {pill.icon && <Ionicons name={pill.icon} size={13} color="#fff" style={{ marginLeft: 4 }} />}
          </View>
          {res && res.status === 'UNVERIFIED' && res.shares ? (
            <Text style={[styles.resultNote, { color: theme.textSub }]} numberOfLines={2}>{res.shares}</Text>
          ) : null}
        </View>
        <View style={{ alignItems: 'flex-end', justifyContent: 'space-between', alignSelf: 'stretch' }}>
          {res && res.status === 'ALLOTTED' ? (
            <Ionicons name="checkmark-circle" size={24} color="#22C55E" />
          ) : res && res.status === 'NON_ALLOTTEE' ? (
            <Ionicons name="close-circle" size={24} color="#EF4444" />
          ) : (
            <View style={{ height: 24 }} />
          )}
          <TouchableOpacity style={[styles.shareBtn, { backgroundColor: theme.innerBox }]} onPress={() => shareStatus(item, res)}>
            <Ionicons name="share-social-outline" size={15} color={theme.textMain} />
            <Text style={[styles.shareBtnText, { color: theme.textMain }]}>Share</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  };

  const subCells = (it) => {
    const sub = it?.subscription || {};
    const cells = [
      ['QIB', sub.qib],
      ['HNI', sub.hni],
      ['RETAIL', sub.retail],
      ['TOTAL', sub.total],
    ];
    // Employee / Shareholder quota — sirf unhi IPOs me jinke liye data aaya ho
    if (sub.emp && sub.emp !== 'N/A' && sub.emp !== '--') cells.push(['EMPLOYEE', sub.emp]);
    if (sub.sh && sub.sh !== 'N/A' && sub.sh !== '--') cells.push(['SHAREHOLDER', sub.sh]);
    return cells;
  };

  const tabs = [
    { key: 'IPO', label: 'Terminal' },
    { key: 'Account', label: 'Vault' },
    { key: 'Allotment', label: 'Allotment' },
  ];

  // ---------------------------------------------------------------------------
  // UI
  // ---------------------------------------------------------------------------
  return (
    <View style={[styles.root, { backgroundColor: theme.bg }]}>
      <StatusBar barStyle={isDarkMode ? 'light-content' : 'dark-content'} backgroundColor={theme.headerBg} />
      <SafeAreaView style={{ flex: 1 }}>
        {/* HEADER */}
        <View style={[styles.topBar, { backgroundColor: theme.headerBg }]}>
          <View style={styles.brandRow}>
            <Text style={[styles.brandText, { color: theme.textMain }]}>IPO</Text>
            <View
              style={[
                styles.liveBar,
                { backgroundColor: liveBarColor, shadowColor: liveBarColor, opacity: blinkOn ? 1 : 0.45 },
              ]}
            />
          </View>
          <View style={styles.topRight}>
            <TouchableOpacity style={[styles.iconBtn, { backgroundColor: theme.innerBox, borderColor: theme.border }]} onPress={() => setSearchModalOpen(true)}>
              <Ionicons name="search-outline" size={19} color={theme.textMain} />
            </TouchableOpacity>
            <TouchableOpacity style={[styles.iconBtn, { backgroundColor: theme.innerBox, borderColor: theme.border }]} onPress={openNotifications}>
              <Ionicons name="notifications-outline" size={19} color={theme.textMain} />
              {unreadNotifCount > 0 && (
                <View style={styles.notifBadge}>
                  <Text style={styles.notifBadgeText}>{unreadNotifCount > 9 ? '9+' : unreadNotifCount}</Text>
                </View>
              )}
            </TouchableOpacity>
            <TouchableOpacity style={[styles.iconBtn, { backgroundColor: theme.innerBox, borderColor: theme.border }]} onPress={() => setSettingsModalOpen(true)}>
              <Ionicons name="settings-outline" size={19} color={theme.textMain} />
            </TouchableOpacity>
          </View>
        </View>

        {/* ===================== TERMINAL ===================== */}
        {activeTab === 'IPO' && (
          <View style={{ flex: 1 }}>
            <View style={styles.pillTabs}>
              {['OPEN', 'UPCOMING', 'CLOSED'].map(tab => {
                const active = statusFilter === tab;
                return (
                  <TouchableOpacity
                    key={tab}
                    style={[styles.pillTab, active && { backgroundColor: theme.accent }]}
                    onPress={() => { setStatusFilter(tab); setHighlightedIpoId(null); }}
                  >
                    <Text style={[styles.pillTabText, { color: active ? '#fff' : theme.accentText }]}>{tab}</Text>
                  </TouchableOpacity>
                );
              })}
            </View>

            <View style={styles.chipsRow}>
              {[
                { key: 'ALL', label: 'All' },
                { key: 'MAINBOARD', label: 'Mainboard' },
                { key: 'SME', label: 'SME' },
              ].map(cat => {
                const active = categoryFilter === cat.key;
                return (
                  <TouchableOpacity
                    key={cat.key}
                    style={[
                      styles.chip,
                      { borderColor: active ? theme.accent : theme.border, backgroundColor: active ? theme.accentSoft : 'transparent' },
                    ]}
                    onPress={() => setCategoryFilter(cat.key)}
                  >
                    <Text style={[styles.chipText, { color: active ? theme.accentText : theme.textMain }]}>{cat.label}</Text>
                  </TouchableOpacity>
                );
              })}
              <Text style={[styles.countText, { color: theme.textSub }]}>{displayList.length} Active IPOs</Text>
            </View>

            {loading ? (
              <View style={styles.centerBox}>
                <ActivityIndicator size="large" color={theme.accent} />
                <Text style={{ color: theme.textSub, marginTop: 12, fontSize: 13 }}>Syncing live market data...</Text>
              </View>
            ) : fetchError && ipos.length === 0 ? (
              <View style={styles.centerBox}>
                <Ionicons name="cloud-offline-outline" size={48} color={theme.textSub} />
                <Text style={{ color: theme.textMain, marginTop: 14, fontSize: 15, fontWeight: '700' }}>Server abhi jaag raha hai</Text>
                <Text style={{ color: theme.textSub, marginTop: 6, fontSize: 12, textAlign: 'center', paddingHorizontal: 30 }}>
                  Free hosting server kuch der inactive rehne par so jaata hai. Pehli request me 30-50 second lag sakte hain.
                </Text>
                <TouchableOpacity
                  style={[styles.primaryBtn, { backgroundColor: theme.accent, marginTop: 18, paddingHorizontal: 40 }]}
                  onPress={() => { setLoading(true); fetchLiveIPOs(); }}
                >
                  <Text style={styles.primaryBtnText}>RETRY</Text>
                </TouchableOpacity>
              </View>
            ) : (
              <FlatList
                data={displayList}
                keyExtractor={item => item.id}
                renderItem={renderIpoCard}
                contentContainerStyle={{ paddingHorizontal: 14, paddingBottom: 20, paddingTop: 4 }}
                refreshControl={
                  <RefreshControl
                    refreshing={refreshing}
                    onRefresh={() => { setRefreshing(true); fetchLiveIPOs(); }}
                    tintColor={theme.accent}
                  />
                }
                ListEmptyComponent={
                  <View style={[styles.centerBox, { marginTop: 60 }]}>
                    <Ionicons name="file-tray-outline" size={40} color={theme.textSub} />
                    <Text style={{ color: theme.textSub, marginTop: 10, fontSize: 13 }}>Is filter me abhi koi IPO nahi hai</Text>
                  </View>
                }
              />
            )}
          </View>
        )}

        {/* ===================== VAULT ===================== */}
        {activeTab === 'Account' && (
          <FlatList
            data={accounts}
            keyExtractor={item => item.id}
            contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 24 }}
            ListHeaderComponent={
              <View>
                <View style={styles.pageTitleRow}>
                  <Text style={[styles.pageTitle, { color: theme.textMain }]}>Vault ({accounts.length})</Text>
                  <TouchableOpacity style={[styles.outlineBtn, { borderColor: theme.accent }]} onPress={() => setAccountModalOpen(true)}>
                    <Text style={[styles.outlineBtnText, { color: theme.accentText }]}>Add PAN</Text>
                  </TouchableOpacity>
                </View>
                <Text style={[styles.pageSub, { color: theme.textSub }]}>Saved Family Accounts</Text>
              </View>
            }
            ListEmptyComponent={
              <Text style={{ color: theme.textSub, textAlign: 'center', padding: 30 }}>Koi account nahi hai. "Add PAN" dabao.</Text>
            }
            renderItem={({ item }) => (
              <View style={[styles.vaultCard, { backgroundColor: theme.cardBg, borderColor: theme.border }]}>
                <Avatar name={item.name} size={46} />
                <View style={{ flex: 1, marginLeft: 12 }}>
                  <Text style={[styles.vaultName, { color: theme.textMain }]} numberOfLines={1}>{item.name}</Text>
                  <Text style={[styles.vaultPan, { color: theme.textSub }]}>PAN: {item.pan}</Text>
                </View>
                <View style={{ alignItems: 'flex-end', justifyContent: 'space-between', alignSelf: 'stretch' }}>
                  {item.accountType ? (
                    <View style={[styles.demateBadge, { backgroundColor: item.accountType === 'NSDL' ? '#6B4416' : '#1E3A66' }]}>
                      <Text style={styles.demateBadgeText}>{item.accountType}</Text>
                    </View>
                  ) : <View style={{ height: 20 }} />}
                  <TouchableOpacity onPress={() => deleteAccount(item)} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
                    <Ionicons name="trash-outline" size={20} color="#F87171" />
                  </TouchableOpacity>
                </View>
              </View>
            )}
          />
        )}

        {/* ===================== ALLOTMENT SCANNER ===================== */}
        {activeTab === 'Allotment' && (
          <FlatList
            data={accounts}
            keyExtractor={item => item.id}
            renderItem={renderAccountResult}
            contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 24 }}
            ListHeaderComponent={
              <View>
                <View style={styles.pageTitleRow}>
                  <Text style={[styles.pageTitle, { color: theme.textMain }]}>Allotment Scanner</Text>
                  <TouchableOpacity onPress={() => setActiveTab('IPO')} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
                    <Ionicons name="close-circle-outline" size={28} color={theme.textSub} />
                  </TouchableOpacity>
                </View>

                <TouchableOpacity
                  style={[styles.targetBox, { borderColor: theme.border, backgroundColor: theme.cardBg }]}
                  onPress={() => setIpoPickerOpen(true)}
                >
                  <Text style={{ flex: 1, color: theme.textSub, fontSize: 15 }} numberOfLines={1}>
                    Target:{' '}
                    <Text style={{ color: theme.textMain, fontWeight: '600' }}>
                      {selectedAllotmentIpo ? selectedAllotmentIpo.name : 'IPO select karo'}
                    </Text>
                  </Text>
                  <Ionicons name="chevron-down" size={20} color={theme.textMain} />
                </TouchableOpacity>

                <TouchableOpacity
                  style={[styles.scanBtn, { backgroundColor: theme.accent, opacity: checkingProgress ? 0.9 : 1 }]}
                  activeOpacity={0.85}
                  onPress={startBatchCheck}
                  disabled={checkingProgress !== null}
                >
                  <Text style={styles.scanBtnTitle}>AUTO-SCAN ({accounts.length} ACCOUNTS)</Text>
                  <View style={{ flexDirection: 'row', alignItems: 'center', marginTop: 3 }}>
                    {checkingProgress ? <ActivityIndicator size="small" color="#fff" style={{ marginRight: 6 }} /> : null}
                    <Text style={styles.scanBtnSub}>{checkingProgress || 'Tap to scan all accounts'}</Text>
                  </View>
                </TouchableOpacity>

                <Text style={[styles.scanHint, { color: theme.textSub }]}>
                  Har account registrar ki site par khud check hota hai (captcha ke liye max {MAX_SCAN_ROUNDS} baar retry).
                </Text>
                {selectedAllotmentIpo && (
                  <TouchableOpacity style={styles.manualLink} onPress={() => openRegistrarSite(selectedAllotmentIpo)}>
                    <Ionicons name="open-outline" size={14} color={theme.accentText} />
                    <Text style={[styles.manualLinkText, { color: theme.accentText }]}>
                      Ya seedha registrar ki official site par check karo
                    </Text>
                  </TouchableOpacity>
                )}
              </View>
            }
          />
        )}

        {/* ===================== BOTTOM TABS ===================== */}
        <View style={[styles.bottomNav, { backgroundColor: theme.headerBg, borderTopColor: theme.border }]}>
          {tabs.map(nav => {
            const active = activeTab === nav.key;
            return (
              <TouchableOpacity key={nav.key} style={styles.bottomNavBtn} onPress={() => setActiveTab(nav.key)}>
                {active && <View style={[styles.navIndicator, { backgroundColor: theme.accent }]} />}
                <Text style={[styles.bottomNavLabel, { color: active ? theme.textMain : theme.textSub, fontWeight: active ? '700' : '500' }]}>
                  {nav.label}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>
      </SafeAreaView>

      {/* ===================== CARD REVERSE (FLIP) POPUP ===================== */}
      <Modal visible={!!backItem} transparent animationType="fade" onRequestClose={closeBack}>
        <TouchableOpacity activeOpacity={1} style={[styles.centerBackdrop, { backgroundColor: theme.backdrop }]} onPress={closeBack}>
          {backItem && (() => {
            const d = detailCache[backItem.id] || {};
            const regName = d.registrar || (backItem.registrar !== 'Not available yet' ? backItem.registrar : null);
            const cells = subCells(backItem);
            const rows = [];
            for (let i = 0; i < cells.length; i += 2) rows.push(cells.slice(i, i + 2));
            const noSubYet = backItem.status === 'UPCOMING';
            return (
              <Animated.View
                onStartShouldSetResponder={() => true}
                style={[
                  styles.backCard,
                  {
                    backgroundColor: theme.modalBg,
                    borderColor: theme.border,
                    opacity: flipAnim,
                    transform: [
                      { perspective: 900 },
                      { rotateY: flipAnim.interpolate({ inputRange: [0, 1], outputRange: ['90deg', '0deg'] }) },
                    ],
                  },
                ]}
              >
                <TouchableOpacity style={styles.backClose} onPress={closeBack} hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}>
                  <Ionicons name="close-circle-outline" size={28} color={theme.textMain} />
                </TouchableOpacity>

                <View style={{ alignItems: 'center', marginTop: 4 }}>
                  <CompanyLogo name={backItem.name} size={80} />
                  <Text style={[styles.backName, { color: theme.textMain }]}>{backItem.name}</Text>
                </View>

                <View style={[styles.divider, { backgroundColor: theme.border }]} />

                <Text style={[styles.backSection, { color: theme.textSub }]}>LIVE SUBSCRIPTION</Text>
                {noSubYet ? (
                  <Text style={{ color: theme.textSub, fontSize: 13, marginTop: 4 }}>Subscription IPO khulne ke baad shuru hogi.</Text>
                ) : (
                  rows.map((row, idx) => (
                    <View key={idx} style={styles.subRow}>
                      {row.map(([label, val]) => (
                        <Text key={label} style={[styles.subCell, { color: theme.textSub }]} numberOfLines={1}>
                          {label}:{' '}
                          <Text style={{ color: label === 'TOTAL' ? theme.good : theme.textMain, fontWeight: '700' }}>
                            {val && val !== 'N/A' ? val : '--'}
                          </Text>
                        </Text>
                      ))}
                    </View>
                  ))
                )}

                <View style={[styles.divider, { backgroundColor: theme.border }]} />

                <Text style={[styles.backSection, { color: theme.textSub }]}>REGISTRAR & LEAD MANAGER</Text>
                <Text style={[styles.backLine, { color: theme.textMain }]}>
                  {regName || (d.loaded ? 'Registrar abhi pata nahi' : 'Loading...')}
                </Text>
                <Text style={[styles.backLine, { color: theme.textMain, marginTop: 6 }]}>
                  {d.lead_managers || (d.loaded ? 'Lead manager abhi pata nahi' : '')}
                </Text>
              </Animated.View>
            );
          })()}
        </TouchableOpacity>
      </Modal>

      {/* ===================== NOTIFICATIONS ===================== */}
      <Modal visible={notifModalOpen} transparent animationType="slide" onRequestClose={() => setNotifModalOpen(false)}>
        <View style={[styles.sheetBackdrop, { backgroundColor: theme.backdrop }]}>
          <View style={[styles.sheet, { backgroundColor: theme.modalBg, borderColor: theme.border }]}>
            <View style={styles.sheetHeader}>
              <View style={{ flex: 1 }}>
                <Text style={[styles.sheetTitle, { color: theme.textMain }]}>Notifications</Text>
                <Text style={[styles.sheetSub, { color: theme.textSub }]}>NEW IPOS, GMP & ALLOTMENT UPDATES</Text>
              </View>
              <TouchableOpacity onPress={() => setNotifModalOpen(false)}>
                <Ionicons name="close-circle" size={26} color={theme.textSub} />
              </TouchableOpacity>
            </View>
            <FlatList
              data={notifications}
              keyExtractor={(item, idx) => `${item.ipo_id}-${item.time}-${idx}`}
              style={{ maxHeight: 460 }}
              ListEmptyComponent={
                <Text style={{ color: theme.textSub, textAlign: 'center', padding: 24 }}>Koi notification abhi tak nahi hai</Text>
              }
              renderItem={({ item }) => (
                <View style={[styles.listRow, { borderBottomColor: theme.border }]}>
                  <Text style={[styles.listRowTitle, { color: theme.textMain }]}>{item.message}</Text>
                  <Text style={[styles.listRowSub, { color: theme.textSub }]}>
                    {new Date(item.time).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
                  </Text>
                </View>
              )}
            />
          </View>
        </View>
      </Modal>

      {/* ===================== SEARCH (top se khulta hai) ===================== */}
      <Modal visible={searchModalOpen} transparent animationType="fade" onRequestClose={() => { setSearchModalOpen(false); setSearchQuery(''); }}>
        <View style={[styles.searchBackdrop, { backgroundColor: theme.backdrop }]}>
          <View style={[styles.searchBox, { backgroundColor: theme.modalBg, borderColor: theme.border }]}>
            <View style={styles.sheetHeader}>
              <View style={{ flex: 1 }}>
                <Text style={[styles.sheetTitle, { color: theme.textMain }]}>Search IPOs</Text>
                <Text style={[styles.sheetSub, { color: theme.textSub }]}>COMPANY KA NAAM LIKHO</Text>
              </View>
              <TouchableOpacity onPress={() => { setSearchModalOpen(false); setSearchQuery(''); }}>
                <Ionicons name="close-circle" size={26} color={theme.textSub} />
              </TouchableOpacity>
            </View>
            <TextInput
              placeholder="e.g. Moneyview, Orient Cables..."
              placeholderTextColor={theme.textSub}
              value={searchQuery}
              onChangeText={setSearchQuery}
              autoFocus
              style={[styles.input, { backgroundColor: theme.innerBox, borderColor: theme.border, color: theme.textMain }]}
            />
            <FlatList
              data={searchResults}
              keyExtractor={item => item.id}
              style={{ maxHeight: 420 }}
              keyboardShouldPersistTaps="handled"
              ListEmptyComponent={
                <Text style={{ color: theme.textSub, textAlign: 'center', padding: 24 }}>
                  {searchQuery.trim() ? 'No matching IPO found' : 'Type a company name to search'}
                </Text>
              }
              renderItem={({ item }) => (
                <TouchableOpacity
                  style={[styles.listRow, { borderBottomColor: theme.border }]}
                  onPress={() => {
                    setActiveTab('IPO');
                    setStatusFilter(item.status);
                    setCategoryFilter('ALL');
                    setHighlightedIpoId(item.id);
                    setSearchModalOpen(false);
                    setSearchQuery('');
                  }}
                >
                  <Text style={[styles.listRowTitle, { color: theme.textMain }]}>{item.name}</Text>
                  <Text style={[styles.listRowSub, { color: theme.textSub }]}>{item.status} • {item.category}</Text>
                </TouchableOpacity>
              )}
            />
          </View>
        </View>
      </Modal>

      {/* ===================== SETTINGS ===================== */}
      <Modal visible={settingsModalOpen} transparent animationType="slide" onRequestClose={() => setSettingsModalOpen(false)}>
        <View style={[styles.sheetBackdrop, { backgroundColor: theme.backdrop }]}>
          <View style={[styles.sheet, { backgroundColor: theme.modalBg, borderColor: theme.border, maxHeight: '88%' }]}>
            <View style={styles.sheetHeader}>
              <View style={{ flex: 1 }}>
                <Text style={[styles.sheetTitle, { color: theme.textMain }]}>Settings</Text>
                <Text style={[styles.sheetSub, { color: theme.textSub }]}>APP PREFERENCES</Text>
              </View>
              <TouchableOpacity onPress={() => setSettingsModalOpen(false)}>
                <Ionicons name="close-circle" size={26} color={theme.textSub} />
              </TouchableOpacity>
            </View>

            <ScrollView showsVerticalScrollIndicator={false}>
              <Text style={[styles.settingsHeading, { color: theme.textMain }]}>Theme</Text>
              {[
                { mode: 'dark', icon: 'moon', title: 'Dark Mode', sub: 'Low light ke liye', active: isDarkMode, color: theme.accentText },
                { mode: 'light', icon: 'sunny', title: 'Light Mode', sub: 'Din ki roshni ke liye', active: !isDarkMode, color: '#F59E0B' },
              ].map(opt => (
                <TouchableOpacity
                  key={opt.mode}
                  style={[styles.themeRow, { backgroundColor: theme.innerBox, borderColor: opt.active ? theme.accent : theme.border }]}
                  onPress={() => setThemeMode(opt.mode)}
                >
                  <Ionicons name={opt.icon} size={20} color={opt.color} style={{ marginRight: 12 }} />
                  <View style={{ flex: 1 }}>
                    <Text style={{ color: theme.textMain, fontWeight: '700', fontSize: 14 }}>{opt.title}</Text>
                    <Text style={{ color: theme.textSub, fontSize: 11, marginTop: 2 }}>{opt.sub}</Text>
                  </View>
                  <Ionicons name={opt.active ? 'radio-button-on' : 'radio-button-off'} size={20} color={opt.active ? theme.accent : theme.textSub} />
                </TouchableOpacity>
              ))}

              <Text style={[styles.settingsHeading, { color: theme.textMain, marginTop: 20 }]}>Phone Notifications</Text>
              <View style={[styles.pushBox, { backgroundColor: theme.innerBox, borderColor: pushStatus.ok ? '#22C55E' : theme.border }]}>
                <View style={{ flexDirection: 'row', alignItems: 'flex-start' }}>
                  <Ionicons
                    name={pushStatus.ok === null ? 'time-outline' : pushStatus.ok ? 'checkmark-circle' : 'alert-circle'}
                    size={20}
                    color={pushStatus.ok === null ? theme.textSub : pushStatus.ok ? '#22C55E' : '#F59E0B'}
                    style={{ marginRight: 10, marginTop: 1 }}
                  />
                  <Text style={{ flex: 1, color: theme.textMain, fontSize: 13, lineHeight: 18 }}>{pushStatus.msg}</Text>
                </View>
                <View style={{ flexDirection: 'row', marginTop: 12 }}>
                  <TouchableOpacity style={[styles.smallBtn, { borderColor: theme.accent }]} onPress={registerForPushNotifications}>
                    <Text style={{ color: theme.accentText, fontWeight: '700', fontSize: 12 }}>Retry setup</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={[styles.smallBtn, { borderColor: theme.accent, marginLeft: 10 }]} onPress={sendTestPush}>
                    <Text style={{ color: theme.accentText, fontWeight: '700', fontSize: 12 }}>Send test push</Text>
                  </TouchableOpacity>
                </View>
                {pushStatus.ok === false && /firebase|fcm/i.test(pushStatus.msg) && (
                  <Text style={{ color: theme.textSub, fontSize: 11, marginTop: 12, lineHeight: 16 }}>
                    Firebase setup: 1) console.firebase.google.com me project banao → Android app add karo (package: com.gautambabariya.ipogmptracker) →
                    google-services.json download karo. 2) Wo file app folder me rakho aur app.json me android.googleServicesFile set karo.
                    3) Terminal: eas credentials → Android → Google Service Account (FCM V1) upload. 4) Phir naya eas build.
                  </Text>
                )}
              </View>
            </ScrollView>
          </View>
        </View>
      </Modal>

      {/* ===================== ADD PAN ===================== */}
      <Modal visible={accountModalOpen} transparent animationType="fade" onRequestClose={() => setAccountModalOpen(false)}>
        <View style={[styles.centerBackdrop, { backgroundColor: theme.backdrop }]}>
          <View style={[styles.formCard, { backgroundColor: theme.modalBg, borderColor: theme.border }]}>
            <Text style={[styles.sheetTitle, { color: theme.textMain }]}>Add Family Account</Text>
            <Text style={[styles.sheetSub, { color: theme.textSub, marginBottom: 12 }]}>VAULT ME NAYA PAN JODO</Text>

            <TextInput
              placeholder="Account Holder Name"
              placeholderTextColor={theme.textSub}
              value={newName}
              onChangeText={setNewName}
              style={[styles.input, { backgroundColor: theme.innerBox, borderColor: theme.border, color: theme.textMain }]}
            />
            <TextInput
              placeholder="PAN Number (e.g. GSXPB6123C)"
              placeholderTextColor={theme.textSub}
              value={newPan}
              onChangeText={setNewPan}
              autoCapitalize="characters"
              maxLength={10}
              style={[styles.input, { backgroundColor: theme.innerBox, borderColor: theme.border, color: theme.textMain }]}
            />

            <Text style={[styles.sheetSub, { color: theme.textSub, marginBottom: 6 }]}>DEMAT ACCOUNT TYPE (OPTIONAL)</Text>
            <View style={{ flexDirection: 'row', marginBottom: 10 }}>
              {['CDSL', 'NSDL'].map(type => {
                const active = newAccountType === type;
                return (
                  <TouchableOpacity
                    key={type}
                    style={[styles.chip, { marginRight: 8, borderColor: active ? theme.accent : theme.border, backgroundColor: active ? theme.accentSoft : 'transparent' }]}
                    onPress={() => setNewAccountType(type)}
                  >
                    <Text style={[styles.chipText, { color: active ? theme.accentText : theme.textMain }]}>{type}</Text>
                  </TouchableOpacity>
                );
              })}
            </View>

            <TextInput
              placeholder="Client ID / Beneficiary Number (optional)"
              placeholderTextColor={theme.textSub}
              value={newClientId}
              onChangeText={setNewClientId}
              style={[styles.input, { backgroundColor: theme.innerBox, borderColor: theme.border, color: theme.textMain }]}
            />
            <TextInput
              placeholder="UPI ID (optional)"
              placeholderTextColor={theme.textSub}
              value={newUpiId}
              onChangeText={setNewUpiId}
              autoCapitalize="none"
              style={[styles.input, { backgroundColor: theme.innerBox, borderColor: theme.border, color: theme.textMain }]}
            />

            <View style={{ flexDirection: 'row', marginTop: 6 }}>
              <TouchableOpacity style={[styles.formBtn, { backgroundColor: theme.innerBox, marginRight: 10 }]} onPress={() => setAccountModalOpen(false)}>
                <Text style={{ color: theme.textSub, fontWeight: '700' }}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.formBtn, { backgroundColor: theme.accent }]} onPress={saveAccount}>
                <Text style={{ color: '#fff', fontWeight: '800' }}>Save PAN</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* ===================== TARGET IPO PICKER ===================== */}
      <Modal visible={ipoPickerOpen} transparent animationType="slide" onRequestClose={() => setIpoPickerOpen(false)}>
        <View style={[styles.sheetBackdrop, { backgroundColor: theme.backdrop }]}>
          <View style={[styles.sheet, { backgroundColor: theme.modalBg, borderColor: theme.border }]}>
            <View style={styles.sheetHeader}>
              <View style={{ flex: 1 }}>
                <Text style={[styles.sheetTitle, { color: theme.textMain }]}>Select Target IPO</Text>
                <Text style={[styles.sheetSub, { color: theme.textSub }]}>SIRF WO IPO JINKA ALLOTMENT AA CHUKA HAI</Text>
              </View>
              <TouchableOpacity onPress={() => setIpoPickerOpen(false)}>
                <Ionicons name="close-circle" size={26} color={theme.textSub} />
              </TouchableOpacity>
            </View>
            <FlatList
              data={allotmentEligibleIpos}
              keyExtractor={item => item.id}
              style={{ maxHeight: 420 }}
              ListEmptyComponent={
                <Text style={{ color: theme.textSub, textAlign: 'center', padding: 20 }}>Abhi kisi IPO ka allotment declare nahi hua</Text>
              }
              renderItem={({ item }) => (
                <TouchableOpacity
                  style={[styles.listRow, { borderBottomColor: theme.border }]}
                  onPress={() => {
                    setSelectedAllotmentIpo(item);
                    setIpoPickerOpen(false);
                    setAllotmentResults({});
                  }}
                >
                  <Text style={[styles.listRowTitle, { color: theme.textMain }]}>{item.name}</Text>
                  <Text style={[styles.listRowSub, { color: theme.textSub }]}>Allotment: {item.allotment_date}</Text>
                </TouchableOpacity>
              )}
            />
          </View>
        </View>
      </Modal>

      {/* ===================== SPLASH (user ki image, ~2 sec) ===================== */}
      {showIntro && (
        <Animated.View pointerEvents="auto" style={[StyleSheet.absoluteFill, { opacity: introOpacity, zIndex: 999, elevation: 999 }]}>
          <Image source={require('./assets/splash.png')} style={StyleSheet.absoluteFill} resizeMode="cover" />
        </Animated.View>
      )}
    </View>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------
const STATUS_TOP = Platform.OS === 'android' ? (StatusBar.currentHeight || 24) : 12;

const styles = StyleSheet.create({
  root: { flex: 1 },

  // header
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingBottom: 12,
    paddingTop: STATUS_TOP + 14,
  },
  brandRow: { flexDirection: 'row', alignItems: 'center' },
  brandText: { fontSize: 30, fontWeight: '600', letterSpacing: 0.5 },
  liveBar: {
    width: 4,
    height: 26,
    borderRadius: 2,
    marginLeft: 8,
    shadowOpacity: 0.9,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 0 },
    elevation: 4,
  },
  topRight: { flexDirection: 'row', alignItems: 'center' },
  iconBtn: {
    width: 42,
    height: 42,
    borderRadius: 13,
    borderWidth: 1,
    justifyContent: 'center',
    alignItems: 'center',
    marginLeft: 8,
  },
  notifBadge: {
    position: 'absolute',
    top: -5,
    right: -5,
    backgroundColor: '#EF4444',
    borderRadius: 9,
    minWidth: 18,
    height: 18,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 3,
  },
  notifBadgeText: { color: '#fff', fontSize: 10, fontWeight: '800' },

  // status tabs
  pillTabs: {
    flexDirection: 'row',
    marginHorizontal: 16,
    marginTop: 6,
    padding: 3,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: 'rgba(164,63,227,0.55)',
  },
  pillTab: { flex: 1, paddingVertical: 10, borderRadius: 21, alignItems: 'center' },
  pillTabText: { fontSize: 14, fontWeight: '700', letterSpacing: 0.6 },

  // category chips
  chipsRow: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, marginTop: 14, marginBottom: 10 },
  chip: { paddingHorizontal: 15, paddingVertical: 7, borderRadius: 18, borderWidth: 1, marginRight: 8 },
  chipText: { fontSize: 14, fontWeight: '500' },
  countText: { marginLeft: 'auto', fontSize: 13 },

  centerBox: { flex: 1, justifyContent: 'center', alignItems: 'center', paddingVertical: 40 },

  // IPO card
  card: { borderRadius: 18, borderWidth: 1, padding: 14, marginBottom: 14 },
  cardTop: { flexDirection: 'row', alignItems: 'flex-start' },
  cardTitleCol: { flex: 1, marginLeft: 12, marginRight: 8 },
  catBadge: { alignSelf: 'flex-start', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 4, marginBottom: 5 },
  catBadgeText: { color: '#fff', fontSize: 10, fontWeight: '800', letterSpacing: 0.6 },
  cardName: { fontSize: 18, fontWeight: '700' },
  dateRow: { flexDirection: 'row', alignItems: 'center', marginTop: 6 },
  dateText: { fontSize: 12.5, marginLeft: 6 },
  flipBtn: { padding: 4 },

  ticker: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderRadius: 11,
    paddingHorizontal: 12,
    paddingVertical: 10,
    marginTop: 14,
  },
  tickerLabelRow: { flexDirection: 'row', alignItems: 'center' },
  tickerDot: { width: 8, height: 8, borderRadius: 4, marginRight: 7 },
  tickerLabel: { fontSize: 15, fontWeight: '500', letterSpacing: 0.3 },
  tickerUpdated: { fontSize: 11.5, marginTop: 4 },
  tickerValue: { fontSize: 24, fontWeight: '700' },
  tickerGain: { fontSize: 11.5, fontWeight: '600', marginTop: 2 },

  specRow: { flexDirection: 'row', marginTop: 14 },
  specCol: { flex: 1, alignItems: 'center', paddingHorizontal: 4 },
  specLabel: { fontSize: 11, letterSpacing: 0.3 },
  specValue: { fontSize: 16, fontWeight: '700', marginTop: 4 },

  profitRow: { flexDirection: 'row', marginTop: 14 },
  profitBox: { flex: 1, borderWidth: 1, borderRadius: 11, paddingVertical: 10, alignItems: 'center', marginHorizontal: 4 },
  profitLabel: { fontSize: 10.5, letterSpacing: 0.3 },
  profitValue: { fontSize: 19, fontWeight: '800', marginTop: 4 },

  footerRow: { flexDirection: 'row', justifyContent: 'space-between', flexWrap: 'wrap', marginTop: 14 },
  footerTxt: { fontSize: 11.5 },
  footerVal: { fontWeight: '700' },

  perfBox: { flexDirection: 'row', borderWidth: 1, borderRadius: 11, marginTop: 14, paddingVertical: 10 },
  perfCol: { flex: 1, alignItems: 'center', paddingHorizontal: 6 },
  perfLabel: { fontSize: 11.5, letterSpacing: 0.3 },
  perfValue: { fontSize: 18, fontWeight: '800', marginTop: 4 },

  primaryBtn: { borderRadius: 26, paddingVertical: 15, alignItems: 'center', marginTop: 14 },
  primaryBtnText: { color: '#fff', fontSize: 15, fontWeight: '800', letterSpacing: 0.6 },
  registrarHint: { fontSize: 11, textAlign: 'center', marginTop: 8 },

  // pages (vault / scanner)
  pageTitleRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 12 },
  pageTitle: { fontSize: 28, fontWeight: '700' },
  pageSub: { fontSize: 15, marginTop: 12, marginBottom: 14 },
  outlineBtn: { borderWidth: 1, borderRadius: 13, paddingHorizontal: 20, paddingVertical: 11 },
  outlineBtnText: { fontSize: 15, fontWeight: '600' },

  vaultCard: { flexDirection: 'row', alignItems: 'center', borderRadius: 14, borderWidth: 1, padding: 14, marginBottom: 12 },
  vaultName: { fontSize: 16, fontWeight: '600', letterSpacing: 0.3 },
  vaultPan: { fontSize: 13.5, marginTop: 3 },
  demateBadge: { paddingHorizontal: 10, paddingVertical: 3, borderRadius: 5 },
  demateBadgeText: { color: '#fff', fontSize: 11, fontWeight: '700' },

  targetBox: { flexDirection: 'row', alignItems: 'center', borderWidth: 1, borderRadius: 14, paddingHorizontal: 14, paddingVertical: 15, marginTop: 18 },
  scanBtn: { borderRadius: 16, paddingVertical: 14, alignItems: 'center', marginTop: 14 },
  scanBtnTitle: { color: '#fff', fontSize: 17, fontWeight: '700', letterSpacing: 0.4 },
  scanBtnSub: { color: 'rgba(255,255,255,0.92)', fontSize: 13 },
  scanHint: { fontSize: 11.5, textAlign: 'center', marginTop: 10, lineHeight: 16 },
  manualLink: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: 10, marginBottom: 6 },
  manualLinkText: { fontSize: 12.5, fontWeight: '600', marginLeft: 6 },

  resultCard: { flexDirection: 'row', alignItems: 'center', borderRadius: 14, borderWidth: 1, padding: 14, marginTop: 12 },
  resultName: { fontSize: 16, fontWeight: '600', letterSpacing: 0.3 },
  resultNote: { fontSize: 11, marginTop: 6 },
  statusPill: { alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, paddingVertical: 5, borderRadius: 14, marginTop: 8 },
  statusPillText: { fontSize: 12.5, fontWeight: '800', letterSpacing: 0.4 },
  shareBtn: { flexDirection: 'row', alignItems: 'center', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 8, marginTop: 8 },
  shareBtnText: { fontSize: 13.5, fontWeight: '600', marginLeft: 6 },

  // bottom tabs
  bottomNav: { flexDirection: 'row', borderTopWidth: 1, paddingBottom: Platform.OS === 'android' ? 26 : 18 },
  bottomNavBtn: { flex: 1, alignItems: 'center', paddingTop: 16, paddingBottom: 6 },
  navIndicator: { position: 'absolute', top: -1, left: '12%', right: '12%', height: 3, borderRadius: 2 },
  bottomNavLabel: { fontSize: 15 },

  // popups
  centerBackdrop: { flex: 1, justifyContent: 'center', paddingHorizontal: 18 },
  backCard: { borderRadius: 20, borderWidth: 1, padding: 20 },
  backClose: { position: 'absolute', top: 12, right: 12, zIndex: 5 },
  backName: { fontSize: 22, fontWeight: '700', textAlign: 'center', marginTop: 12 },
  divider: { height: 1, marginVertical: 16 },
  backSection: { fontSize: 14, letterSpacing: 0.6, marginBottom: 8 },
  subRow: { flexDirection: 'row', marginTop: 8 },
  subCell: { flex: 1, fontSize: 16 },
  backLine: { fontSize: 15, fontWeight: '500' },

  sheetBackdrop: { flex: 1, justifyContent: 'flex-end' },
  sheet: { borderTopLeftRadius: 22, borderTopRightRadius: 22, borderWidth: 1, padding: 18, paddingBottom: 28 },
  sheetHeader: { flexDirection: 'row', alignItems: 'center', marginBottom: 12 },
  sheetTitle: { fontSize: 19, fontWeight: '800' },
  sheetSub: { fontSize: 11, letterSpacing: 0.6, marginTop: 2 },
  listRow: { paddingVertical: 13, borderBottomWidth: 1 },
  listRowTitle: { fontSize: 15, fontWeight: '600' },
  listRowSub: { fontSize: 12, marginTop: 3 },

  searchBackdrop: { flex: 1, justifyContent: 'flex-start' },
  searchBox: {
    marginTop: STATUS_TOP + 70,
    marginHorizontal: 12,
    borderRadius: 18,
    borderWidth: 1,
    padding: 16,
    maxHeight: '75%',
  },
  input: { borderWidth: 1, borderRadius: 11, paddingHorizontal: 14, paddingVertical: 11, fontSize: 14, marginBottom: 10 },

  settingsHeading: { fontSize: 14, fontWeight: '800', marginBottom: 10, marginTop: 4 },
  themeRow: { flexDirection: 'row', alignItems: 'center', borderWidth: 1, borderRadius: 13, padding: 14, marginBottom: 10 },
  pushBox: { borderWidth: 1, borderRadius: 13, padding: 14 },
  smallBtn: { borderWidth: 1, borderRadius: 10, paddingHorizontal: 14, paddingVertical: 8 },

  formCard: { borderRadius: 20, borderWidth: 1, padding: 18 },
  formBtn: { flex: 1, borderRadius: 12, paddingVertical: 13, alignItems: 'center' },
});
