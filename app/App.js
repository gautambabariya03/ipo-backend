import AsyncStorage from '@react-native-async-storage/async-storage';
import LoginScreen from './LoginScreen';
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  SafeAreaView,
  View,
  Text,
  FlatList,
  TouchableOpacity,
  TextInput,
  RefreshControl,
  StyleSheet,
  ActivityIndicator,
  StatusBar,
  Linking,
  Share,
} from 'react-native';

const BACKEND_URL = 'https://ipo-backend-fpjo.onrender.com/api/ipos/live';

function MainOriginalApp() {
  const [ipos, setIpos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedTab, setSelectedTab] = useState('OPEN'); // OPEN | UPCOMING | CLOSED
  const [selectedCategory, setSelectedCategory] = useState('ALL'); // ALL | MAINBOARD | SME
  const [searchQuery, setSearchQuery] = useState('');

  // 1. Data Fetch Function
  const fetchLiveIPOs = useCallback(async (isManualRefresh = false) => {
    try {
      if (isManualRefresh) setRefreshing(true);
      const res = await fetch(`${BACKEND_URL}?force_refresh=${isManualRefresh}`);
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) {
          setIpos(data);
        }
      }
    } catch (err) {
      console.log('Error fetching live IPOs:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  // 2. Initial Mount + 30-Second Automatic Polling (With Cleanup)
  useEffect(() => {
    fetchLiveIPOs();

    const intervalId = setInterval(() => {
      fetchLiveIPOs(false);
    }, 30000); // Har 30 second me background refresh

    return () => clearInterval(intervalId);
  }, [fetchLiveIPOs]);

  // 3. Tab & Category Filtering
  const filteredIPOs = useMemo(() => {
    return ipos.filter((item) => {
      // Tab filter
      const itemStatus = (item.status || 'OPEN').toUpperCase();
      const tabMatch = itemStatus === selectedTab;

      // Category filter
      const itemCategory = (item.category || 'MAINBOARD').toUpperCase();
      const catMatch =
        selectedCategory === 'ALL' || itemCategory === selectedCategory;

      // Search filter
      const searchMatch =
        searchQuery.trim() === '' ||
        (item.name &&
          item.name.toLowerCase().includes(searchQuery.toLowerCase()));

      return tabMatch && catMatch && searchMatch;
    });
  }, [ipos, selectedTab, selectedCategory, searchQuery]);

  // Share functionality
  const handleShare = (item) => {
    Share.share({
      message: `${item.name} (${item.category})\nDate: ${item.date_range}\nGMP: ₹${item.gmp} (${item.gmp_percentage}%)\nPrice: ${item.price}`,
    });
  };

  // Render IPO Card
  const renderItem = ({ item }) => {
    const isMainboard = item.category === 'MAINBOARD';
    return (
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <Text style={styles.companyName} numberOfLines={1}>
            {item.name}
          </Text>
          <View
            style={[
              styles.badge,
              isMainboard ? styles.badgeMainboard : styles.badgeSme,
            ]}
          >
            <Text style={styles.badgeText}>{item.category}</Text>
          </View>
        </View>

        <View style={styles.dateRow}>
          <Text style={styles.dateText}>📅 {item.date_range}</Text>
        </View>

        {/* Live GMP Banner */}
        <View style={styles.gmpBanner}>
          <View>
            <Text style={styles.gmpTitle}>LIVE GMP TICKER</Text>
            <Text style={styles.lastHeardText}>Updated: {item.last_heard}</Text>
          </View>
          <View style={{ alignItems: 'flex-end' }}>
            <Text style={styles.gmpValue}>
              {item.gmp > 0 ? `+₹${item.gmp}` : item.gmp === 0 ? '--' : `₹${item.gmp}`}
            </Text>
            <Text style={styles.gmpPercent}>
              {item.gmp_percentage > 0 ? `+${item.gmp_percentage}%` : 'NOT DECLARED'}
            </Text>
          </View>
        </View>

        {/* Info Grid */}
        <View style={styles.grid}>
          <View style={styles.gridCol}>
            <Text style={styles.gridLabel}>ISSUE PRICE</Text>
            <Text style={styles.gridValue}>{item.price}</Text>
          </View>
          <View style={styles.gridCol}>
            <Text style={styles.gridLabel}>LOT SIZE</Text>
            <Text style={styles.gridValue}>{item.lot_size} sh</Text>
          </View>
          <View style={styles.gridCol}>
            <Text style={styles.gridLabel}>ISSUE SIZE</Text>
            <Text style={styles.gridValue}>{item.issue_size}</Text>
          </View>
        </View>

        {/* Profit Grid */}
        <View style={styles.grid}>
          <View style={styles.gridCol}>
            <Text style={styles.gridLabel}>EST. RETAIL PROFIT</Text>
            <Text style={[styles.gridValue, { color: '#00e676' }]}>
              {item.retail_profit > 0 ? `₹${item.retail_profit}` : '--'}
            </Text>
          </View>
          <View style={styles.gridCol}>
            <Text style={styles.gridLabel}>EST. HNI PROFIT</Text>
            <Text style={[styles.gridValue, { color: '#00e676' }]}>
              {item.hni_profit > 0 ? `₹${item.hni_profit}` : '--'}
            </Text>
          </View>
        </View>

        {/* Footer Dates */}
        <View style={styles.cardFooter}>
          <Text style={styles.footerDate}>Allotment: {item.allotment_date}</Text>
          <Text style={styles.footerDate}>Listing: {item.listing_date}</Text>
        </View>

        {/* Action Buttons */}
        <View style={styles.actionRow}>
          <TouchableOpacity
            style={styles.actionButtonOutline}
            onPress={() => handleShare(item)}
          >
            <Text style={styles.outlineButtonText}>SHARE</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.actionButtonPrimary}
            onPress={() =>
              Linking.openURL('https://zerodha.com/open-account').catch(() => {})
            }
          >
            <Text style={styles.primaryButtonText}>APPLY IPO</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  };

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor="#0B0F19" />

      {/* Top App Header */}
      <View style={styles.topHeader}>
        <View>
          <Text style={styles.appTitle}>APEX IPO</Text>
          <Text style={styles.appSubTitle}>TERMINAL PRO</Text>
        </View>
        <TextInput
          style={styles.searchInput}
          placeholder="Search IPO..."
          placeholderTextColor="#64748B"
          value={searchQuery}
          onChangeText={setSearchQuery}
        />
      </View>

      {/* Status Tabs: OPEN / UPCOMING / CLOSED */}
      <View style={styles.tabContainer}>
        {['OPEN', 'UPCOMING', 'CLOSED'].map((tab) => (
          <TouchableOpacity
            key={tab}
            style={[styles.tabButton, selectedTab === tab && styles.tabButtonActive]}
            onPress={() => setSelectedTab(tab)}
          >
            {tab === 'OPEN' && <View style={styles.onlineDot} />}
            <Text
              style={[
                styles.tabText,
                selectedTab === tab && styles.tabTextActive,
              ]}
            >
              {tab}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Category Pills: ALL / MAINBOARD / SME */}
      <View style={styles.catContainer}>
        <View style={{ flexDirection: 'row' }}>
          {['ALL', 'MAINBOARD', 'SME'].map((cat) => (
            <TouchableOpacity
              key={cat}
              style={[
                styles.catPill,
                selectedCategory === cat && styles.catPillActive,
              ]}
              onPress={() => setSelectedCategory(cat)}
            >
              <Text
                style={[
                  styles.catText,
                  selectedCategory === cat && styles.catTextActive,
                ]}
              >
                {cat}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
        <Text style={styles.countText}>{filteredIPOs.length} IPOs</Text>
      </View>

      {/* List or Loader */}
      {loading ? (
        <View style={styles.centerContainer}>
          <ActivityIndicator size="large" color="#00e676" />
          <Text style={styles.loadingText}>Fetching live IPO records...</Text>
        </View>
      ) : (
        <FlatList
          data={filteredIPOs}
          keyExtractor={(item) => item.id || item.name}
          renderItem={renderItem}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => fetchLiveIPOs(true)}
              tintColor="#00e676"
              colors={['#00e676']}
            />
          }
          ListEmptyComponent={
            <View style={styles.centerContainer}>
              <Text style={styles.emptyText}>
                No {selectedTab} IPOs found for {selectedCategory}.
              </Text>
            </View>
          }
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0B0F19',
  },
  topHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#1E293B',
  },
  appTitle: {
    color: '#F8FAFC',
    fontSize: 18,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
  appSubTitle: {
    color: '#00e676',
    fontSize: 10,
    fontWeight: '700',
  },
  searchInput: {
    width: '45%',
    height: 36,
    backgroundColor: '#161F30',
    borderRadius: 8,
    paddingHorizontal: 10,
    color: '#F8FAFC',
    fontSize: 12,
  },
  tabContainer: {
    flexDirection: 'row',
    backgroundColor: '#111827',
    padding: 6,
    marginHorizontal: 16,
    marginTop: 12,
    borderRadius: 12,
  },
  tabButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 10,
    borderRadius: 8,
  },
  tabButtonActive: {
    backgroundColor: '#10B981',
  },
  onlineDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: '#00e676',
    marginRight: 6,
  },
  tabText: {
    color: '#94A3B8',
    fontWeight: '700',
    fontSize: 13,
  },
  tabTextActive: {
    color: '#0B0F19',
  },
  catContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    marginVertical: 12,
  },
  catPill: {
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 6,
    backgroundColor: '#161F30',
    marginRight: 8,
  },
  catPillActive: {
    borderWidth: 1,
    borderColor: '#00e676',
    backgroundColor: 'rgba(0, 230, 118, 0.1)',
  },
  catText: {
    color: '#94A3B8',
    fontSize: 12,
    fontWeight: '600',
  },
  catTextActive: {
    color: '#00e676',
  },
  countText: {
    color: '#64748B',
    fontSize: 12,
  },
  listContent: {
    paddingHorizontal: 16,
    paddingBottom: 24,
  },
  card: {
    backgroundColor: '#131B2E',
    borderRadius: 14,
    padding: 14,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: '#1E293B',
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  companyName: {
    color: '#F8FAFC',
    fontSize: 16,
    fontWeight: '700',
    flex: 1,
    marginRight: 8,
  },
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  badgeMainboard: {
    backgroundColor: '#1D4ED8',
  },
  badgeSme: {
    backgroundColor: '#D97706',
  },
  badgeText: {
    color: '#FFFFFF',
    fontSize: 10,
    fontWeight: '800',
  },
  dateRow: {
    marginVertical: 6,
  },
  dateText: {
    color: '#94A3B8',
    fontSize: 12,
  },
  gmpBanner: {
    backgroundColor: '#0F291E',
    borderWidth: 1,
    borderColor: '#00e676',
    borderRadius: 8,
    padding: 10,
    marginVertical: 8,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  gmpTitle: {
    color: '#00e676',
    fontSize: 10,
    fontWeight: '800',
  },
  lastHeardText: {
    color: '#64748B',
    fontSize: 10,
  },
  gmpValue: {
    color: '#00e676',
    fontSize: 16,
    fontWeight: '800',
  },
  gmpPercent: {
    color: '#00e676',
    fontSize: 10,
    fontWeight: '700',
  },
  grid: {
    flexDirection: 'row',
    backgroundColor: '#0B0F19',
    borderRadius: 8,
    paddingVertical: 8,
    paddingHorizontal: 10,
    marginTop: 6,
  },
  gridCol: {
    flex: 1,
  },
  gridLabel: {
    color: '#64748B',
    fontSize: 9,
    fontWeight: '700',
  },
  gridValue: {
    color: '#F8FAFC',
    fontSize: 12,
    fontWeight: '700',
    marginTop: 2,
  },
  cardFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 10,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: '#1E293B',
  },
  footerDate: {
    color: '#64748B',
    fontSize: 11,
  },
  actionRow: {
    flexDirection: 'row',
    marginTop: 12,
  },
  actionButtonOutline: {
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#334155',
    marginRight: 8,
  },
  outlineButtonText: {
    color: '#94A3B8',
    fontWeight: '700',
    fontSize: 12,
  },
  actionButtonPrimary: {
    flex: 1,
    backgroundColor: '#2563EB',
    paddingVertical: 10,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  primaryButtonText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 13,
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: 60,
  },
  loadingText: {
    color: '#94A3B8',
    marginTop: 10,
    fontSize: 13,
  },
  emptyText: {
    color: '#64748B',
    fontSize: 14,
  },
});

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = React.useState(null);

  React.useEffect(() => {
    (async () => {
      try {
        const user = await AsyncStorage.getItem('user_phone_number');
        setIsAuthenticated(!!user);
      } catch (e) {
        setIsAuthenticated(false);
      }
    })();
  }, []);

  if (isAuthenticated === null) return null;
  if (!isAuthenticated) return <LoginScreen onLoginSuccess={() => setIsAuthenticated(true)} />;
  return <MainOriginalApp />;
}