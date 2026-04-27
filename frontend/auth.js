/**
 * Frontend Authentication Module
 * Handles client-side authentication logic including token management,
 * login/register, and authenticated API calls with auto-refresh on 401.
 *
 * Usage: Auth.login(email, password)
 *        Auth.fetch(endpoint, options) // Use instead of plain fetch for authenticated calls
 */

const Auth = (() => {
    const TOKEN_KEY = 'auth_token';
    const REFRESH_TOKEN_KEY = 'refresh_token';
    const API_BASE = window.location.origin + '/api';

    /**
     * Get current access token from localStorage
     * @returns {string|null} Access token or null if not authenticated
     */
    const getToken = () => {
        return localStorage.getItem(TOKEN_KEY);
    };

    /**
     * Check if user is authenticated
     * @returns {boolean} True if access token exists
     */
    const isAuthenticated = () => {
        return getToken() !== null;
    };

    /**
     * Require authentication - redirect to login if not authenticated
     * @throws Does not throw, redirects browser
     */
    const requireAuth = () => {
        if (!isAuthenticated()) {
            window.location.href = '/login';
        }
    };

    /**
     * Register new user with email and password
     * @param {string} email User email address
     * @param {string} password User password
     * @returns {Promise<Object>} Response from server with id, email, message
     * @throws {Error} Throws error with message from API or network error
     */
    const register = async (email, password) => {
        const response = await window.fetch(`${API_BASE}/auth/register`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ email, password })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Registration failed');
        }

        return data;
    };

    /**
     * Login user with email and password
     * Stores access and refresh tokens in localStorage
     * @param {string} email User email address
     * @param {string} password User password
     * @returns {Promise<Object>} Response with access_token, refresh_token, token_type, expires_in
     * @throws {Error} Throws error with message from API or network error
     */
    const login = async (email, password) => {
        const response = await window.fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ email, password })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Login failed');
        }

        // Store tokens in localStorage
        localStorage.setItem(TOKEN_KEY, data.access_token);
        localStorage.setItem(REFRESH_TOKEN_KEY, data.refresh_token);

        return data;
    };

    /**
     * Logout user - clears tokens and redirects to login
     * @throws Does not throw, clears localStorage and redirects
     */
    const logout = async () => {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(REFRESH_TOKEN_KEY);
        // In browser environment, redirect; in test environment, just clear
        if (typeof window !== 'undefined' && window.location) {
            try {
                window.location.href = '/login';
            } catch (e) {
                // Navigation not available in test environment
            }
        }
    };

    /**
     * Refresh access token using refresh token
     * Updates stored access token on success
     * @returns {Promise<Object>} Response with new access_token, token_type, expires_in
     * @throws {Error} Throws error if refresh token missing or API error
     */
    const refreshToken = async () => {
        const refreshTokenValue = localStorage.getItem(REFRESH_TOKEN_KEY);

        if (!refreshTokenValue) {
            throw new Error('No refresh token available');
        }

        const response = await window.fetch(`${API_BASE}/auth/refresh`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ refresh_token: refreshTokenValue })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Token refresh failed');
        }

        // Store new access token
        localStorage.setItem(TOKEN_KEY, data.access_token);

        return data;
    };

    /**
     * Make authenticated fetch request with auto-refresh on 401
     * Wrapper for fetch() that adds Authorization header and handles token expiration
     * @param {string} endpoint API endpoint (e.g., '/applications', '/emails')
     * @param {Object} options Fetch options (method, headers, body, etc.)
     * @returns {Promise<Object>} Parsed JSON response from API
     * @throws {Error} Throws error if not authenticated or API error
     */
    const fetch = async (endpoint, options = {}) => {
        const token = getToken();

        if (!token) {
            throw new Error('Not authenticated - please login first');
        }

        // Merge default headers with custom headers
        const headers = {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
            ...(options.headers || {})
        };

        const fetchOptions = {
            ...options,
            headers
        };

        let response = await window.fetch(`${API_BASE}${endpoint}`, fetchOptions);

        // Handle 401 - token expired, try to refresh and retry
        if (response.status === 401) {
            try {
                await refreshToken();

                // Retry request with new token
                const newToken = getToken();
                fetchOptions.headers['Authorization'] = `Bearer ${newToken}`;
                response = await window.fetch(`${API_BASE}${endpoint}`, fetchOptions);
            } catch (error) {
                // Refresh token is also expired – session is completely invalid
                const refreshTokenValue = localStorage.getItem(REFRESH_TOKEN_KEY);
                const isRefreshExpired = refreshTokenValue === null ||
                    /refresh token|expired/i.test(error.message || '');

                if (isRefreshExpired) {
                    // Clear tokens and logout
                    await logout();
                    throw new Error('SESSION_EXPIRED');
                }

                throw new Error(error.message || 'Token refresh failed, please login again');
            }
        }

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || `API error: ${response.status}`);
        }

        return data;
    };

    /**
     * Get current user data
     * Fetches user info from /api/auth/me endpoint
     * @returns {Promise<Object>} User object with id, email, is_admin, created_at
     * @throws {Error} Throws error if not authenticated or API error
     */
    const getCurrentUser = async () => {
        return await fetch('/auth/me');
    };

    /**
     * Check if current user is admin
     * First fetches user data, then returns is_admin flag
     * @returns {Promise<boolean>} True if user is admin
     */
    const isAdmin = async () => {
        try {
            const user = await getCurrentUser();
            return user.is_admin === true;
        } catch (error) {
            return false;
        }
    };

    // Public API
    return {
        getToken,
        isAuthenticated,
        requireAuth,
        register,
        login,
        logout,
        refreshToken,
        fetch,
        getCurrentUser,
        isAdmin
    };
})();

// Export for Node.js testing environment
if (typeof module !== 'undefined' && module.exports) {
    module.exports = Auth;
}
