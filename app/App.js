import React, { useState, useEffect } from 'react';
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
  Alert
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Ionicons } from '@expo/vector-icons';
const BASE_URL = 'https://ipo-backend-fpjo.onrender.com';
const API_URL = `${BASE_URL}/api/ipos/live`;
const ALLOTMENT_API = `${BASE_URL}/api/allotment/check-batch`;

export default function App() {
  const [ipos, setIpos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Theme State: Dark / Light
  const [isDarkMode, setIsDarkMode] = useState(true);
  const [settingsModalOpen, setSettingsModalOpen] = useState(false);

  // Tabs
  const [activeTab, setActiveTab] = useState('IPO'); // IPO, Account, Allotment
  const [statusFilter, setStatusFilter] = useState('OPEN'); // OPEN, UPCOMING, CLOSED
  const [categoryFilter, setCategoryFilter] = useState('ALL'); // ALL, MAINBOARD, SME

  // Visible Blinking Dot Pulse
  const [blinkOn, setBlinkOn] = useState(true);

  // Modals
  const [selectedIpo, setSelectedIpo] = useState(null);
  const [detailModalOpen, setDetailModalOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);

  // Notifications (new IPO / GMP change / status change feed)
  const [notifications, setNotifications] = useState([]);
  const [notifModalOpen, setNotifModalOpen] = useState(false);
  const [unreadNotifCount, setUnreadNotifCount] = useState(0);

  // Accounts (Vault)
  const [accounts, setAccounts] = useState([]);
  const [accountModalOpen, setAccountModalOpen] = useState(false);
  const [newName, setNewName] = useState('');
  const [newPan, setNewPan] = useState('');

  // Live Backend Allotment Batch
  const [selectedAllotmentIpo, setSelectedAllotmentIpo] = useState(null);
  const [ipoPickerOpen, setIpoPickerOpen] = useState(false);
  const [checkingProgress, setCheckingProgress] = useState(null);
  const [allotmentResults, setAllotmentResults] = useState({});

  useEffect(() => {
    const timer = setInterval(() => {
      setBlinkOn(prev => !prev);
    }, 600);

    loadSavedAccounts();
    loadSavedTheme();
    fetchLiveIPOs();
    fetchNotifications();

    return () => clearInterval(timer);
  }, []);

  // REAL-TIME AUTO REFRESH: backend re-scrapes investorgain every 10 min in the
  // background, but that new data only reaches the screen if the app asks for
  // it. This polls the API every 30s so OPEN/UPCOMING/CLOSED tabs and GMP
  // values update on their own, without the user pulling to refresh.
  useEffect(() => {
    const pollTimer = setInterval(() => {
      fetchLiveIPOs();
      fetchNotifications();
    }, 30000); // 30 seconds

    return () => clearInterval(pollTimer);
  }, []);

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

  const loadSavedTheme = async () => {
    try {
      const savedTheme = await AsyncStorage.getItem('@app_theme');
      if (savedTheme !== null) {
        setIsDarkMode(savedTheme === 'dark');
      }
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
      { id: Date.now().toString(), name: newName.toUpperCase().trim(), pan: newPan.toUpperCase().trim() }
    ];
    setAccounts(updated);
    await AsyncStorage.setItem('@family_accounts', JSON.stringify(updated));
    setNewName('');
    setNewPan('');
    setAccountModalOpen(false);
  };

  const deleteAccount = async (id) => {
    const updated = accounts.filter(x => x.id !== id);
    setAccounts(updated);
    await AsyncStorage.setItem('@family_accounts', JSON.stringify(updated));
  };

  const fetchLiveIPOs = async () => {
    try {
      const resp = await fetch(API_URL);
      const data = await resp.json();
      setIpos(data);
      if (!selectedAllotmentIpo) {
        const firstEligible = data.find(x => x.status === 'CLOSED' && x.allotment_declared);
        if (firstEligible) setSelectedAllotmentIpo(firstEligible);
      }
    } catch (e) {
      console.log('Fetch Error:', e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  // REAL LIVE BACKEND BATCH ENGINE
  const startBatchCheck = async () => {
    if (accounts.length === 0) {
      Alert.alert('No Accounts', 'Please add at least one account in Vault');
      return;
    }
    if (!selectedAllotmentIpo) {
      Alert.alert('Select IPO', 'Please select an IPO first');
      return;
    }

    setCheckingProgress(`Scanning ${accounts.length} Accounts with Registrar...`);

    try {
      const resp = await fetch(ALLOTMENT_API, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ipo_name: selectedAllotmentIpo.name,
          lot_size: selectedAllotmentIpo.lot_size || 50,
          accounts: accounts.map(a => ({ id: a.id, name: a.name, pan: a.pan }))
        })
      });

      const data = await resp.json();
      if (data.success) {
        setAllotmentResults(data.results);
      } else {
        Alert.alert('Error', 'Registrar server response failed');
      }
    } catch (e) {
      console.log('Allotment Engine Error:', e);
      Alert.alert('Connection Error', 'Could not reach the server to check allotment. Please try again.');
    } finally {
      setCheckingProgress(null);
    }
  };

  const recheckSingleAccount = async (accId) => {
    if (!selectedAllotmentIpo) return;
    const targetAcc = accounts.find(a => a.id === accId);
    if (!targetAcc) return;

    try {
      const resp = await fetch(ALLOTMENT_API, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ipo_name: selectedAllotmentIpo.name,
          lot_size: selectedAllotmentIpo.lot_size || 50,
          accounts: [{ id: targetAcc.id, name: targetAcc.name, pan: targetAcc.pan }]
        })
      });
      const data = await resp.json();
      if (data.success && data.results[accId]) {
        setAllotmentResults(prev => ({ ...prev, [accId]: data.results[accId] }));
      }
    } catch (e) {
      console.log('Recheck Error:', e);
      setAllotmentResults(prev => ({
        ...prev,
        [accId]: { status: 'CHECK_FAILED', shares: 'Could not reach registrar' }
      }));
    }
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

  const displayList = ipos.filter(item => {
    const matchStatus = item.status === statusFilter;
    const matchCategory = categoryFilter === 'ALL' || item.category === categoryFilter;
    return matchStatus && matchCategory;
  });

  // Allotment check sirf un IPOs ke liye valid hai jo CLOSED ho chuke hain
  // AUR jinka allotment date already aa chuka hai — OPEN/UPCOMING IPOs ya
  // aise CLOSED IPOs jinka allotment abhi aana baaki hai, list me nahi aayenge.
  const allotmentEligibleIpos = ipos.filter(
    item => item.status === 'CLOSED' && item.allotment_declared
  );

  const theme = {
    bg: isDarkMode ? '#0B0F19' : '#F3F4F6',
    cardBg: isDarkMode ? '#111827' : '#FFFFFF',
    textMain: isDarkMode ? '#F8FAFC' : '#111827',
    textSub: isDarkMode ? '#94A3B8' : '#6B7280',
    border: isDarkMode ? '#1F2937' : '#E5E7EB',
    headerBg: isDarkMode ? '#0B0F19' : '#FFFFFF',
    innerBox: isDarkMode ? '#1E293B' : '#F9FAFB',
    specKey: isDarkMode ? '#94A3B8' : '#6B7280',
    specVal: isDarkMode ? '#F8FAFC' : '#1F2937',
    terminalBg: isDarkMode ? '#064E3B' : '#ECFDF5',
    terminalBorder: isDarkMode ? '#059669' : '#A7F3D0',
    terminalText: isDarkMode ? '#34D399' : '#059669'
  };

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: theme.bg }]}>
      <StatusBar barStyle={isDarkMode ? 'light-content' : 'dark-content'} backgroundColor={theme.headerBg} />

      {/* TOP HEADER */}
      <View style={[styles.topBar, { backgroundColor: theme.headerBg, borderBottomColor: theme.border }]}>
        <View style={{ flexDirection: 'row', alignItems: 'center' }}>
          <View style={[styles.radarIconBox, { backgroundColor: theme.innerBox, borderColor: theme.border }]}>
            <View style={[styles.radarDot, { opacity: blinkOn ? 1 : 0.2 }]} />
          </View>
          <View>
            <Text style={[styles.appName, { color: theme.textMain }]}>APEX IPO</Text>
            <Text style={styles.appSub}>TERMINAL PRO</Text>
          </View>
        </View>

        <View style={styles.topRightActions}>
          <TouchableOpacity style={[styles.iconBtn, { backgroundColor: theme.innerBox, marginRight: 8 }]}>
            <Ionicons name="search-outline" size={18} color={theme.textSub} />
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.iconBtn, { backgroundColor: theme.innerBox, marginRight: 8 }]}
            onPress={openNotifications}
          >
            <Ionicons name="notifications-outline" size={18} color={theme.textSub} />
            {unreadNotifCount > 0 && (
              <View style={styles.notifBadge}>
                <Text style={styles.notifBadgeText}>{unreadNotifCount > 9 ? '9+' : unreadNotifCount}</Text>
              </View>
            )}
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.iconBtn, { backgroundColor: theme.innerBox }]}
            onPress={() => setSettingsModalOpen(true)}
          >
            <Ionicons name="settings-outline" size={18} color={theme.textSub} />
          </TouchableOpacity>
        </View>
      </View>

      {/* IPO TAB */}
      {activeTab === 'IPO' && (
        <View style={{ flex: 1 }}>
          <View style={[styles.pillTabBar, { backgroundColor: theme.bg }]}>
            {['OPEN', 'UPCOMING', 'CLOSED'].map(tab => {
              const isActive = statusFilter === tab;
              return (
                <TouchableOpacity
                  key={tab}
                  style={[
                    styles.pillTabBtn,
                    { backgroundColor: theme.innerBox },
                    isActive && styles.pillTabBtnActive
                  ]}
                  onPress={() => setStatusFilter(tab)}
                >
                  <Text style={[styles.pillTabText, { color: theme.textSub }, isActive && styles.pillTabTextActive]}>
                    {tab === 'OPEN' ? '🟢 OPEN' : tab}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>

          <View style={[styles.filterChipRow, { borderBottomColor: theme.border }]}>
            <View style={{ flexDirection: 'row' }}>
              {[
                { key: 'ALL', label: 'All' },
                { key: 'MAINBOARD', label: 'Mainboard' },
                { key: 'SME', label: 'SME' }
              ].map(cat => {
                const isSelected = categoryFilter === cat.key;
                return (
                  <TouchableOpacity
                    key={cat.key}
                    style={[
                      styles.chip,
                      { backgroundColor: theme.innerBox },
                      isSelected && styles.chipActive
                    ]}
                    onPress={() => setCategoryFilter(cat.key)}
                  >
                    <Text style={[styles.chipText, { color: theme.textSub }, isSelected && styles.chipTextActive]}>
                      {cat.label}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>
            <Text style={{ color: theme.textSub, fontSize: 11, fontWeight: '700' }}>
              {displayList.length} Active IPOs
            </Text>
          </View>

          {loading ? (
            <View style={styles.centerBox}>
              <ActivityIndicator size="large" color="#10B981" />
              <Text style={{ color: theme.textSub, marginTop: 12, fontSize: 13 }}>Syncing Live Market GMP...</Text>
            </View>
          ) : (
            <FlatList
              data={displayList}
              keyExtractor={item => item.id}
              contentContainerStyle={{ padding: 12, paddingBottom: 25 }}
              refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); fetchLiveIPOs(); }} tintColor="#10B981" />}
              renderItem={({ item }) => {
                const hasGmp = item.gmp > 0;
                const isClosed = item.status === 'CLOSED';

                return (
                  <View style={[styles.cardContainer, { backgroundColor: theme.cardBg, borderColor: theme.border }]}>
                    <View style={styles.cardHeader}>
                      <View style={{ flex: 1 }}>
                        <Text style={[styles.cardTitle, { color: theme.textMain }]} numberOfLines={1}>{item.name}</Text>
                        <Text style={[styles.cardDateRange, { color: theme.textSub }]}>📅 {item.date_range}</Text>
                      </View>
                      <View style={[styles.tagBadge, item.category === 'SME' ? styles.tagSme : styles.tagMain]}>
                        <Text style={styles.tagBadgeText}>{item.category}</Text>
                      </View>
                    </View>

                    <View style={[styles.gmpTerminalBox, { backgroundColor: theme.terminalBg, borderColor: theme.terminalBorder }]}>
                      <View>
                        <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                          <View
                            style={[
                              styles.liveBlinkCircle,
                              { backgroundColor: blinkOn ? '#10B981' : '#064E3B' }
                            ]}
                          />
                          <Text style={styles.gmpTerminalLabel}>LIVE GMP TICKER</Text>
                        </View>
                        <Text style={[styles.lastHeardText, { color: isDarkMode ? '#A7F3D0' : '#065F46' }]}>Updated: {item.last_heard}</Text>
                      </View>

                      <View style={{ alignItems: 'flex-end' }}>
                        <Text style={[styles.gmpMainValue, { color: theme.terminalText }, !hasGmp && { color: theme.textSub }]}>
                          {hasGmp ? `+₹${item.gmp}` : '--'}
                        </Text>
                        <Text style={[styles.gmpPctBadge, { color: theme.terminalText }, !hasGmp && { color: theme.textSub }]}>
                          {hasGmp ? `${item.gmp_percentage}% EST. GAIN` : 'NOT DECLARED'}
                        </Text>
                      </View>
                    </View>

                    <View style={[styles.specGrid, { backgroundColor: theme.innerBox }]}>
                      <View style={styles.specCol}>
                        <Text style={[styles.specKey, { color: theme.specKey }]}>ISSUE PRICE</Text>
                        <Text style={[styles.specVal, { color: theme.specVal }]}>{item.price}</Text>
                      </View>
                      <View style={styles.specCol}>
                        <Text style={[styles.specKey, { color: theme.specKey }]}>LOT SIZE</Text>
                        <Text style={[styles.specVal, { color: theme.specVal }]}>{item.lot_size} sh</Text>
                      </View>
                      <View style={styles.specCol}>
                        <Text style={[styles.specKey, { color: theme.specKey }]}>ISSUE SIZE</Text>
                        <Text style={[styles.specVal, { color: theme.specVal }]}>{item.issue_size}</Text>
                      </View>
                    </View>

                    {isClosed ? (
                      <View style={[styles.closedPerformanceBox, { backgroundColor: theme.innerBox }]}>
                        <View style={{ flex: 1 }}>
                          <Text style={[styles.specKey, { color: theme.specKey }]}>LISTING PRICE</Text>
                          <Text style={styles.greenHighlight}>{item.listing_price}</Text>
                        </View>
                        <View style={{ flex: 1, alignItems: 'flex-end' }}>
                          <Text style={[styles.specKey, { color: theme.specKey }]}>CURRENT CMP (BSE)</Text>
                          <Text style={styles.greenHighlight}>{item.current_price}</Text>
                        </View>
                      </View>
                    ) : (
                      <View style={[styles.profitBanner, { backgroundColor: theme.innerBox }]}>
                        <View style={{ flex: 1 }}>
                          <Text style={[styles.specKey, { color: theme.specKey }]}>EST. RETAIL PROFIT</Text>
                          <Text style={styles.profitAmount}>
                            {hasGmp ? `₹${item.retail_profit.toLocaleString('en-IN')}` : '--'}
                          </Text>
                        </View>
                        <View style={{ flex: 1, alignItems: 'flex-end' }}>
                          <Text style={[styles.specKey, { color: theme.specKey }]}>EST. HNI PROFIT</Text>
                          <Text style={styles.profitAmount}>
                            {hasGmp ? `₹${item.hni_profit.toLocaleString('en-IN')}` : '--'}
                          </Text>
                        </View>
                      </View>
                    )}

                    <View style={styles.timelineRow}>
                      <Text style={[styles.timelineText, { color: theme.textSub }]}>Allotment: <Text style={{ color: theme.textMain, fontWeight: 'bold' }}>{item.allotment_date}</Text></Text>
                      <Text style={[styles.timelineText, { color: theme.textSub }]}>Listing: <Text style={{ color: theme.textMain, fontWeight: 'bold' }}>{item.listing_date}</Text></Text>
                    </View>

                    <View style={styles.actionRow}>
                      <TouchableOpacity
                        style={[styles.detailsBtn, { backgroundColor: theme.innerBox, borderColor: theme.border }]}
                        onPress={() => {
                          setSelectedIpo(item);
                          setDetailModalOpen(true);
                          setDetailLoading(true);
                          fetch(`${BASE_URL}/api/ipos/detail/${item.id}`)
                            .then(r => r.json())
                            .then(detail => {
                              setSelectedIpo(prev => (prev && prev.id === item.id) ? {
                                ...prev,
                                registrar: detail?.registrar?.name || 'Not available',
                                lead_managers: (detail?.lead_managers && detail.lead_managers.length > 0)
                                  ? detail.lead_managers.join(', ')
                                  : 'Not available',
                              } : prev);
                            })
                            .catch(() => {})
                            .finally(() => setDetailLoading(false));
                        }}
                      >
                        <Text style={[styles.detailsBtnText, { color: theme.textMain }]}>VIEW INSIGHTS</Text>
                      </TouchableOpacity>

                      <TouchableOpacity style={styles.shareIconBtn}>
                        <Ionicons name="share-social-outline" size={16} color="#38BDF8" />
                      </TouchableOpacity>

                      {isClosed ? (
                        <TouchableOpacity
                          style={[styles.primaryActionBtn, { backgroundColor: '#10B981' }]}
                          onPress={() => {
                            setSelectedAllotmentIpo(item);
                            setActiveTab('Allotment');
                          }}
                        >
                          <Text style={styles.primaryBtnText}>CHECK ALLOTMENT</Text>
                        </TouchableOpacity>
                      ) : (
                        <TouchableOpacity style={styles.primaryActionBtn}>
                          <Text style={styles.primaryBtnText}>APPLY IPO</Text>
                        </TouchableOpacity>
                      )}
                    </View>
                  </View>
                );
              }}
            />
          )}
        </View>
      )}

      {/* ACCOUNTS TAB */}
      {activeTab === 'Account' && (
        <View style={{ flex: 1, padding: 14 }}>
          <View style={styles.accountHeader}>
            <View>
              <Text style={[styles.accountTitle, { color: theme.textMain }]}>Family Vault ({accounts.length})</Text>
              <Text style={[styles.accountSub, { color: theme.textSub }]}>Manage Demat & PANs for Instant Allotments</Text>
            </View>
            <TouchableOpacity style={styles.addPanBtn} onPress={() => setAccountModalOpen(true)}>
              <Ionicons name="add" size={18} color="#0B0F19" />
              <Text style={styles.addPanText}>Add PAN</Text>
            </TouchableOpacity>
          </View>

          <FlatList
            data={accounts}
            keyExtractor={item => item.id}
            renderItem={({ item }) => (
              <View style={[styles.accountCard, { backgroundColor: theme.cardBg, borderColor: theme.border }]}>
                <View>
                  <Text style={[styles.panHolderName, { color: theme.textMain }]}>{item.name}</Text>
                  <Text style={[styles.panNumber, { color: theme.textSub }]}>{item.pan}</Text>
                </View>
                <TouchableOpacity style={styles.deleteBtn} onPress={() => deleteAccount(item.id)}>
                  <Ionicons name="trash-outline" size={18} color="#EF4444" />
                </TouchableOpacity>
              </View>
            )}
          />
        </View>
      )}

      {/* ALLOTMENT TAB */}
      {activeTab === 'Allotment' && (
        <View style={{ flex: 1, padding: 14 }}>
          <TouchableOpacity
            style={[styles.ipoSelectBtn, { backgroundColor: theme.cardBg, borderColor: theme.border }]}
            onPress={() => setIpoPickerOpen(true)}
          >
            <View>
              <Text style={[styles.specKey, { color: theme.specKey }]}>TARGET IPO</Text>
              <Text style={[styles.selectedIpoName, { color: theme.textMain }]}>
                {selectedAllotmentIpo ? selectedAllotmentIpo.name : 'Select an IPO'}
              </Text>
            </View>
            <Ionicons name="chevron-down" size={20} color={theme.textSub} />
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.batchTriggerBtn}
            onPress={startBatchCheck}
            disabled={checkingProgress !== null}
          >
            {checkingProgress ? (
              <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                <ActivityIndicator color="#FFF" size="small" style={{ marginRight: 8 }} />
                <Text style={styles.primaryBtnText}>{checkingProgress}</Text>
              </View>
            ) : (
              <Text style={styles.primaryBtnText}>
                SCAN ALLOTMENT ({accounts.length} ACCOUNTS)
              </Text>
            )}
          </TouchableOpacity>

          <FlatList
            data={accounts}
            keyExtractor={item => item.id}
            renderItem={({ item }) => {
              const res = allotmentResults[item.id];
              const isAllotted = res?.status === 'ALLOTTED';

              return (
                <View style={[styles.allotCardItem, { backgroundColor: theme.cardBg, borderColor: theme.border }]}>
                  <View style={{ flex: 1 }}>
                    <Text style={[styles.panHolderName, { color: theme.textMain }]}>{item.name}</Text>
                    <Text style={[styles.panNumber, { color: theme.textSub }]}>{item.pan}</Text>
                  </View>

                  <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                    <View style={[
                      styles.statusPill,
                      isAllotted ? styles.statusAllotted : styles.statusNotApplied
                    ]}>
                      <Text style={[
                        styles.statusPillText,
                        isAllotted ? { color: '#10B981' } : { color: theme.textSub }
                      ]}>
                        {res ? res.shares : 'Awaiting Scan'}
                      </Text>
                    </View>

                    <TouchableOpacity
                      style={{ padding: 6, marginLeft: 6 }}
                      onPress={() => recheckSingleAccount(item.id)}
                    >
                      <Ionicons name="reload-outline" size={16} color={theme.textSub} />
                    </TouchableOpacity>

                    <TouchableOpacity
                      style={{ padding: 6, marginLeft: 2 }}
                      onPress={() => shareStatus(item, res)}
                    >
                      <Ionicons name="share-social-outline" size={16} color="#0284C7" />
                    </TouchableOpacity>
                  </View>
                </View>
              );
            }}
          />
        </View>
      )}

      {/* BOTTOM NAVBAR */}
      <View style={[styles.bottomNavbar, { backgroundColor: theme.headerBg, borderTopColor: theme.border }]}>
        {[
          { key: 'IPO', icon: 'stats-chart', label: 'Terminal' },
          { key: 'Account', icon: 'wallet-outline', label: 'Vault' },
          { key: 'Allotment', icon: 'shield-checkmark-outline', label: 'Allotment' }
        ].map(nav => {
          const isActive = activeTab === nav.key;
          return (
            <TouchableOpacity
              key={nav.key}
              style={styles.bottomNavBtn}
              onPress={() => setActiveTab(nav.key)}
            >
              <Ionicons
                name={nav.icon}
                size={20}
                color={isActive ? '#10B981' : theme.textSub}
              />
              <Text style={[styles.bottomNavLabel, { color: theme.textSub }, isActive && styles.bottomNavLabelActive]}>
                {nav.label}
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>

      {/* SETTINGS MODAL */}
      <Modal visible={settingsModalOpen} transparent animationType="slide">
        <View style={styles.modalBackdrop}>
          <View style={[styles.sheetBox, { backgroundColor: theme.cardBg }]}>
            <View style={styles.sheetTop}>
              <View style={{ flex: 1 }}>
                <Text style={[styles.sheetTitle, { color: theme.textMain }]}>Settings</Text>
                <Text style={[styles.specKey, { color: theme.specKey }]}>APP PREFERENCES</Text>
              </View>
              <TouchableOpacity onPress={() => setSettingsModalOpen(false)}>
                <Ionicons name="close-circle" size={24} color={theme.textSub} />
              </TouchableOpacity>
            </View>

            <Text style={[styles.subHeaderTitle, { color: theme.textMain }]}>Theme Appearance</Text>
            
            <TouchableOpacity
              style={[
                styles.themeOptionRow,
                { backgroundColor: theme.innerBox, borderColor: isDarkMode ? '#10B981' : theme.border }
              ]}
              onPress={() => setThemeMode('dark')}
            >
              <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                <Ionicons name="moon" size={20} color="#10B981" style={{ marginRight: 12 }} />
                <View>
                  <Text style={[styles.themeOptionTitle, { color: theme.textMain }]}>Dark Mode (Terminal Pro)</Text>
                  <Text style={[styles.specKey, { color: theme.specKey }]}>Obsidian slate theme for low light</Text>
                </View>
              </View>
              <Ionicons
                name={isDarkMode ? "radio-button-on" : "radio-button-off"}
                size={20}
                color={isDarkMode ? "#10B981" : theme.textSub}
              />
            </TouchableOpacity>

            <TouchableOpacity
              style={[
                styles.themeOptionRow,
                { backgroundColor: theme.innerBox, borderColor: !isDarkMode ? '#10B981' : theme.border, marginTop: 10 }
              ]}
              onPress={() => setThemeMode('light')}
            >
              <View style={{ flexDirection: 'row', alignItems: 'center' }}>
                <Ionicons name="sunny" size={20} color="#F59E0B" style={{ marginRight: 12 }} />
                <View>
                  <Text style={[styles.themeOptionTitle, { color: theme.textMain }]}>Light Mode (Classic Clean)</Text>
                  <Text style={[styles.specKey, { color: theme.specKey }]}>Bright daylight readability</Text>
                </View>
              </View>
              <Ionicons
                name={!isDarkMode ? "radio-button-on" : "radio-button-off"}
                size={20}
                color={!isDarkMode ? "#10B981" : theme.textSub}
              />
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.modalCloseBtn, { marginTop: 20 }]}
              onPress={() => setSettingsModalOpen(false)}
            >
              <Text style={styles.primaryBtnText}>DONE</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* FINANCIAL DETAILS MODAL */}
      <Modal visible={detailModalOpen} transparent animationType="slide">
        <View style={styles.modalBackdrop}>
          <View style={[styles.sheetBox, { backgroundColor: theme.cardBg }]}>
            <View style={styles.sheetTop}>
              <View style={{ flex: 1 }}>
                <Text style={[styles.sheetTitle, { color: theme.textMain }]}>{selectedIpo?.name}</Text>
                <Text style={[styles.specKey, { color: theme.specKey }]}>DETAILED ALLOCATION & SUBSCRIPTION</Text>
              </View>
              <TouchableOpacity onPress={() => setDetailModalOpen(false)}>
                <Ionicons name="close-circle" size={24} color={theme.textSub} />
              </TouchableOpacity>
            </View>

            <ScrollView showsVerticalScrollIndicator={false}>
              <Text style={[styles.subHeaderTitle, { color: theme.textMain }]}>Live Subscription Multipliers</Text>
              <View style={[styles.darkTable, { borderColor: theme.border }]}>
                <View style={[styles.darkTableRowHead, { backgroundColor: theme.innerBox }]}>
                  <Text style={[styles.tableHeadTxt, { color: theme.textSub }]}>Category</Text>
                  <Text style={[styles.tableHeadTxt, { color: theme.textSub }]}>Times (x)</Text>
                </View>
                <View style={[styles.darkTableRow, { borderColor: theme.border }]}><Text style={[styles.tableTxt, { color: theme.textSub }]}>QIB (Institutional)</Text><Text style={[styles.tableTxtBold, { color: theme.textMain }]}>{selectedIpo?.subscription?.qib || 'N/A'}</Text></View>
                <View style={[styles.darkTableRow, { borderColor: theme.border }]}><Text style={[styles.tableTxt, { color: theme.textSub }]}>HNI / NII</Text><Text style={[styles.tableTxtBold, { color: theme.textMain }]}>{selectedIpo?.subscription?.hni || 'N/A'}</Text></View>
                <View style={[styles.darkTableRow, { borderColor: theme.border }]}><Text style={[styles.tableTxt, { color: theme.textSub }]}>Retail Public</Text><Text style={[styles.tableTxtBold, { color: theme.textMain }]}>{selectedIpo?.subscription?.retail || 'N/A'}</Text></View>
                <View style={[styles.darkTableRow, { backgroundColor: theme.terminalBg, borderColor: theme.border }]}><Text style={[styles.tableTxtBold, { color: '#10B981' }]}>Total Subscription</Text><Text style={[styles.tableTxtBold, { color: '#10B981' }]}>{selectedIpo?.subscription?.total || 'N/A'}</Text></View>
              </View>

              <Text style={[styles.subHeaderTitle, { color: theme.textMain }]}>Registrar & Legal Info</Text>
              {detailLoading && (
                <Text style={[styles.specKey, { color: theme.specKey, marginBottom: 6 }]}>Loading live details…</Text>
              )}
              <View style={[styles.legalInfoBox, { backgroundColor: theme.innerBox }]}>
                <View style={styles.specRow}><Text style={[styles.specKey, { color: theme.specKey }]}>REGISTRAR</Text><Text style={[styles.legalVal, { color: theme.textMain }]}>{selectedIpo?.registrar || '--'}</Text></View>
                <View style={styles.specRow}><Text style={[styles.specKey, { color: theme.specKey }]}>LEAD MANAGER(S)</Text><Text style={[styles.legalVal, { color: theme.textMain }]}>{selectedIpo?.lead_managers || '--'}</Text></View>
                <View style={styles.specRow}><Text style={[styles.specKey, { color: theme.specKey }]}>ANCHOR ALLOCATION</Text><Text style={[styles.legalVal, { color: theme.textMain }]}>{selectedIpo?.anchor || '--'}</Text></View>
              </View>
            </ScrollView>

            <TouchableOpacity style={styles.modalCloseBtn} onPress={() => setDetailModalOpen(false)}>
              <Text style={styles.primaryBtnText}>CLOSE INSIGHTS</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* NOTIFICATIONS MODAL */}
      <Modal visible={notifModalOpen} transparent animationType="slide">
        <View style={styles.modalBackdrop}>
          <View style={[styles.sheetBox, { backgroundColor: theme.cardBg }]}>
            <View style={styles.sheetTop}>
              <View style={{ flex: 1 }}>
                <Text style={[styles.sheetTitle, { color: theme.textMain }]}>Notifications</Text>
                <Text style={[styles.specKey, { color: theme.specKey }]}>NEW IPOS & GMP UPDATES</Text>
              </View>
              <TouchableOpacity onPress={() => setNotifModalOpen(false)}>
                <Ionicons name="close-circle" size={24} color={theme.textSub} />
              </TouchableOpacity>
            </View>

            <FlatList
              data={notifications}
              keyExtractor={(item, idx) => `${item.ipo_id}-${item.time}-${idx}`}
              ListEmptyComponent={
                <Text style={{ color: theme.textSub, textAlign: 'center', padding: 24 }}>
                  Koi notification abhi tak nahi hai
                </Text>
              }
              renderItem={({ item }) => (
                <View style={[styles.pickerRow, { borderBottomColor: theme.border }]}>
                  <Text style={[styles.pickerTitle, { color: theme.textMain }]}>{item.message}</Text>
                  <Text style={[styles.specKey, { color: theme.specKey }]}>
                    {new Date(item.time).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
                  </Text>
                </View>
              )}
            />
          </View>
        </View>
      </Modal>

      {/* ADD ACCOUNT MODAL */}
      <Modal visible={accountModalOpen} transparent animationType="fade">
        <View style={styles.modalBackdrop}>
          <View style={[styles.addAccountModalCard, { backgroundColor: theme.cardBg }]}>
            <Text style={[styles.sheetTitle, { color: theme.textMain }]}>Add Family PAN</Text>
            <Text style={[styles.specKey, { color: theme.specKey, marginBottom: 12 }]}>SECURE LOCAL STORAGE</Text>

            <TextInput
              placeholder="Full Name (e.g. GAUTAM BABARIYA)"
              placeholderTextColor={theme.textSub}
              value={newName}
              onChangeText={setNewName}
              style={[styles.darkInput, { backgroundColor: theme.innerBox, borderColor: theme.border, color: theme.textMain }]}
            />
            <TextInput
              placeholder="PAN Number (e.g. GSXPB6123C)"
              placeholderTextColor={theme.textSub}
              value={newPan}
              onChangeText={setNewPan}
              autoCapitalize="characters"
              style={[styles.darkInput, { backgroundColor: theme.innerBox, borderColor: theme.border, color: theme.textMain }]}
            />

            <View style={{ flexDirection: 'row', marginTop: 12 }}>
              <TouchableOpacity
                style={[styles.modalActionBtn, { backgroundColor: theme.innerBox, marginRight: 10 }]}
                onPress={() => setAccountModalOpen(false)}
              >
                <Text style={{ color: theme.textSub, fontWeight: 'bold' }}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.modalActionBtn, { backgroundColor: '#10B981' }]}
                onPress={saveAccount}
              >
                <Text style={styles.primaryBtnText}>Save Account</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* SELECT IPO FOR ALLOTMENT MODAL */}
      <Modal visible={ipoPickerOpen} transparent animationType="slide">
        <View style={styles.modalBackdrop}>
          <View style={[styles.sheetBox, { backgroundColor: theme.cardBg, maxHeight: '75%' }]}>
            <Text style={[styles.subHeaderTitle, { color: theme.textMain }]}>Select Target IPO</Text>
            <FlatList
              data={allotmentEligibleIpos}
              keyExtractor={item => item.id}
              renderItem={({ item }) => (
                <TouchableOpacity
                  style={[styles.pickerRow, { borderBottomColor: theme.border }]}
                  onPress={() => {
                    setSelectedAllotmentIpo(item);
                    setIpoPickerOpen(false);
                    setAllotmentResults({});
                  }}
                >
                  <Text style={[styles.pickerTitle, { color: theme.textMain }]}>{item.name}</Text>
                  <Text style={[styles.specKey, { color: theme.specKey }]}>{item.status} | Allotment: {item.allotment_date}</Text>
                </TouchableOpacity>
              )}
              ListEmptyComponent={
                <Text style={{ color: theme.textSub, textAlign: 'center', padding: 20 }}>
                  No IPO with declared allotment yet
                </Text>
              }
            />
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1
  },
  radarIconBox: {
    width: 32,
    height: 32,
    borderRadius: 8,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 10,
    borderWidth: 1
  },
  radarDot: { width: 10, height: 10, borderRadius: 5, backgroundColor: '#10B981' },
  appName: { fontSize: 14, fontWeight: '900', letterSpacing: 1.5 },
  appSub: { fontSize: 9, fontWeight: '800', color: '#10B981', letterSpacing: 1 },
  topRightActions: { flexDirection: 'row', alignItems: 'center' },
  iconBtn: {
    width: 32,
    height: 32,
    borderRadius: 8,
    justifyContent: 'center',
    alignItems: 'center'
  },
  notifBadge: {
    position: 'absolute',
    top: -4,
    right: -4,
    backgroundColor: '#EF4444',
    borderRadius: 9,
    minWidth: 18,
    height: 18,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 3,
  },
  notifBadgeText: { color: '#fff', fontSize: 10, fontWeight: '800' },
  pillTabBar: {
    flexDirection: 'row',
    paddingHorizontal: 14,
    paddingVertical: 10
  },
  pillTabBtn: {
    flex: 1,
    paddingVertical: 8,
    alignItems: 'center',
    borderRadius: 10,
    marginHorizontal: 3
  },
  pillTabBtnActive: { backgroundColor: '#10B981' },
  pillTabText: { fontSize: 11, fontWeight: '800' },
  pillTabTextActive: { color: '#0B0F19' },
  filterChipRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderBottomWidth: 1
  },
  chip: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 6,
    marginRight: 8
  },
  chipActive: { borderWidth: 1, borderColor: '#10B981' },
  chipText: { fontSize: 11, fontWeight: '700' },
  chipTextActive: { color: '#10B981' },
  centerBox: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  cardContainer: {
    borderRadius: 14,
    padding: 14,
    marginBottom: 12,
    borderWidth: 1
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 10
  },
  cardTitle: { fontSize: 16, fontWeight: '800' },
  cardDateRange: { fontSize: 11, marginTop: 3 },
  tagBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6 },
  tagMain: { backgroundColor: '#1E3A8A' },
  tagSme: { backgroundColor: '#854D0E' },
  tagBadgeText: { fontSize: 10, fontWeight: '900', color: '#F8FAFC' },
  gmpTerminalBox: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 12,
    borderRadius: 10,
    borderWidth: 1,
    marginBottom: 10
  },
  liveBlinkCircle: { width: 8, height: 8, borderRadius: 4, marginRight: 6 },
  gmpTerminalLabel: { fontSize: 10, fontWeight: '900', color: '#10B981', letterSpacing: 1 },
  lastHeardText: { fontSize: 10, marginTop: 2 },
  gmpMainValue: { fontSize: 20, fontWeight: '900' },
  gmpPctBadge: { fontSize: 10, fontWeight: '800' },
  specGrid: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    padding: 10,
    borderRadius: 8,
    marginBottom: 8
  },
  specCol: { flex: 1 },
  specKey: { fontSize: 9, fontWeight: '800', letterSpacing: 0.5 },
  specVal: { fontSize: 12, fontWeight: '800', marginTop: 2 },
  profitBanner: {
    flexDirection: 'row',
    padding: 10,
    borderRadius: 8,
    marginBottom: 8
  },
  profitAmount: { fontSize: 14, fontWeight: '900', color: '#10B981', marginTop: 2 },
  closedPerformanceBox: {
    flexDirection: 'row',
    padding: 10,
    borderRadius: 8,
    marginBottom: 8
  },
  greenHighlight: { fontSize: 12, fontWeight: '900', color: '#10B981', marginTop: 2 },
  timelineRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 10
  },
  timelineText: { fontSize: 10 },
  actionRow: { flexDirection: 'row', alignItems: 'center' },
  detailsBtn: {
    borderWidth: 1,
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: 8
  },
  detailsBtnText: { fontSize: 10, fontWeight: '800' },
  shareIconBtn: {
    width: 32,
    height: 32,
    borderRadius: 8,
    backgroundColor: '#0369A1',
    justifyContent: 'center',
    alignItems: 'center',
    marginHorizontal: 8
  },
  primaryActionBtn: {
    flex: 1,
    backgroundColor: '#2563EB',
    paddingVertical: 9,
    borderRadius: 8,
    alignItems: 'center'
  },
  primaryBtnText: { fontSize: 11, fontWeight: '900', color: '#FFF', letterSpacing: 0.5 },
  accountHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 14
  },
  accountTitle: { fontSize: 16, fontWeight: '900' },
  accountSub: { fontSize: 11 },
  addPanBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#10B981',
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8
  },
  addPanText: { fontSize: 11, fontWeight: 'bold', color: '#0B0F19', marginLeft: 4 },
  accountCard: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 12,
    borderRadius: 10,
    marginBottom: 8,
    borderWidth: 1
  },
  panHolderName: { fontSize: 13, fontWeight: '800' },
  panNumber: { fontSize: 11, marginTop: 2 },
  deleteBtn: { padding: 6 },
  ipoSelectBtn: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 12,
    borderRadius: 10,
    marginBottom: 10,
    borderWidth: 1
  },
  selectedIpoName: { fontSize: 14, fontWeight: '800', marginTop: 2 },
  batchTriggerBtn: {
    backgroundColor: '#10B981',
    paddingVertical: 12,
    borderRadius: 10,
    alignItems: 'center',
    marginBottom: 12
  },
  allotCardItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 12,
    borderRadius: 10,
    marginBottom: 8,
    borderWidth: 1
  },
  statusPill: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6 },
  statusAllotted: { backgroundColor: '#064E3B' },
  statusNotApplied: { backgroundColor: '#1E293B' },
  statusPillText: { fontSize: 11, fontWeight: '800' },
  bottomNavbar: {
    flexDirection: 'row',
    borderTopWidth: 1,
    paddingVertical: 8
  },
  bottomNavBtn: { flex: 1, alignItems: 'center' },
  bottomNavLabel: { fontSize: 10, marginTop: 2, fontWeight: '700' },
  bottomNavLabelActive: { color: '#10B981' },
  modalBackdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.75)', justifyContent: 'flex-end' },
  sheetBox: { borderTopLeftRadius: 18, borderTopRightRadius: 18, padding: 16, maxHeight: '80%' },
  sheetTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  sheetTitle: { fontSize: 16, fontWeight: '900' },
  subHeaderTitle: { fontSize: 12, fontWeight: '800', marginTop: 10, marginBottom: 8 },
  themeOptionRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 14,
    borderRadius: 10,
    borderWidth: 1.5
  },
  themeOptionTitle: { fontSize: 13, fontWeight: '800' },
  darkTable: { borderWidth: 1, borderRadius: 8, overflow: 'hidden', marginBottom: 12 },
  darkTableRowHead: { flexDirection: 'row', justifyContent: 'space-between', padding: 8 },
  tableHeadTxt: { fontSize: 11, fontWeight: 'bold' },
  darkTableRow: { flexDirection: 'row', justifyContent: 'space-between', padding: 8, borderTopWidth: 1 },
  tableTxt: { fontSize: 12 },
  tableTxtBold: { fontSize: 12, fontWeight: 'bold' },
  legalInfoBox: { padding: 10, borderRadius: 8, marginBottom: 14 },
  specRow: { flexDirection: 'row', justifyContent: 'space-between', marginVertical: 3 },
  legalVal: { fontSize: 11, fontWeight: '700' },
  modalCloseBtn: { backgroundColor: '#10B981', paddingVertical: 10, borderRadius: 8, alignItems: 'center', marginTop: 8 },
  addAccountModalCard: { borderRadius: 14, padding: 18, marginHorizontal: 20, marginBottom: 100 },
  darkInput: { borderWidth: 1, borderRadius: 8, padding: 10, marginBottom: 10, fontSize: 13 },
  modalActionBtn: { flex: 1, paddingVertical: 10, alignItems: 'center', borderRadius: 8 },
  pickerRow: { paddingVertical: 12, borderBottomWidth: 1 },
  pickerTitle: { fontSize: 14, fontWeight: '800' }
});