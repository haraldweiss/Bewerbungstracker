/**
 * Test Suite for Auth Module (TDD)
 * Tests for frontend authentication module with token management
 */

// Mock window.location.origin for the Auth module
global.window = {
    location: {
        origin: 'http://localhost'
    }
};

const Auth = require('./auth.js');

describe('Auth Module', () => {
    const TOKEN_KEY = 'auth_token';
    const REFRESH_TOKEN_KEY = 'refresh_token';

    beforeEach(() => {
        // Clear localStorage before each test
        localStorage.clear();
        // Mock fetch globally
        global.fetch = jest.fn();
    });

    afterEach(() => {
        jest.clearAllMocks();
    });

    describe('getToken()', () => {
        test('should return null when no token exists', () => {
            expect(Auth.getToken()).toBeNull();
        });

        test('should return stored access token', () => {
            localStorage.setItem(TOKEN_KEY, 'test-token-123');
            expect(Auth.getToken()).toBe('test-token-123');
        });
    });

    describe('isAuthenticated()', () => {
        test('should return false when no token exists', () => {
            expect(Auth.isAuthenticated()).toBe(false);
        });

        test('should return true when token exists', () => {
            localStorage.setItem(TOKEN_KEY, 'test-token-123');
            expect(Auth.isAuthenticated()).toBe(true);
        });
    });

    describe('register()', () => {
        test('should POST to /api/auth/register with credentials', async () => {
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({ id: 1, email: 'test@example.com', message: 'User created' })
            });

            const result = await Auth.register('test@example.com', 'password123');

            expect(global.fetch).toHaveBeenCalledWith(
                expect.stringContaining('/api/auth/register'),
                expect.objectContaining({
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email: 'test@example.com', password: 'password123' })
                })
            );
            expect(result).toEqual({ id: 1, email: 'test@example.com', message: 'User created' });
        });

        test('should throw error on registration failure', async () => {
            global.fetch.mockResolvedValueOnce({
                ok: false,
                json: async () => ({ error: 'Email already exists' })
            });

            await expect(Auth.register('test@example.com', 'password123'))
                .rejects
                .toThrow('Email already exists');
        });

        test('should throw error on network failure', async () => {
            global.fetch.mockRejectedValueOnce(new Error('Network error'));

            await expect(Auth.register('test@example.com', 'password123'))
                .rejects
                .toThrow('Network error');
        });
    });

    describe('login()', () => {
        test('should POST to /api/auth/login and store tokens', async () => {
            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    access_token: 'access-123',
                    refresh_token: 'refresh-456',
                    token_type: 'Bearer',
                    expires_in: 3600
                })
            });

            const result = await Auth.login('test@example.com', 'password123');

            expect(global.fetch).toHaveBeenCalledWith(
                expect.stringContaining('/api/auth/login'),
                expect.objectContaining({
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email: 'test@example.com', password: 'password123' })
                })
            );

            expect(localStorage.getItem(TOKEN_KEY)).toBe('access-123');
            expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBe('refresh-456');
            expect(result).toEqual({ access_token: 'access-123', refresh_token: 'refresh-456', token_type: 'Bearer', expires_in: 3600 });
        });

        test('should throw error on login failure', async () => {
            global.fetch.mockResolvedValueOnce({
                ok: false,
                json: async () => ({ error: 'Invalid credentials' })
            });

            await expect(Auth.login('test@example.com', 'wrong-password'))
                .rejects
                .toThrow('Invalid credentials');
        });
    });

    describe('logout()', () => {
        test('should clear tokens from localStorage', async () => {
            localStorage.setItem(TOKEN_KEY, 'test-token-123');
            localStorage.setItem(REFRESH_TOKEN_KEY, 'test-refresh-456');

            await Auth.logout();

            expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
            expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBeNull();
        });

        test('should clear all user-specific data keys (no leak between users)', async () => {
            // User A loggt ein, hat CV + Comparisons + Bewerbungen
            localStorage.setItem(TOKEN_KEY, 'token-A');
            localStorage.setItem('cvData', JSON.stringify({text: 'CV von User A'}));
            localStorage.setItem('cvComparisons', JSON.stringify([{id: 1}]));
            localStorage.setItem('bewerbungsTrackerV3', JSON.stringify({bewerbungen: []}));
            localStorage.setItem('customAIPlatforms', JSON.stringify([{id: 'x'}]));
            localStorage.setItem('jdModalDismissed', '1');
            localStorage.setItem('masterPasswordSet', '1');
            // Nicht-User-spezifisch — sollte erhalten bleiben
            localStorage.setItem('colorScheme', 'dark');

            await Auth.logout();

            // Alle User-Daten weg
            expect(localStorage.getItem('cvData')).toBeNull();
            expect(localStorage.getItem('cvComparisons')).toBeNull();
            expect(localStorage.getItem('bewerbungsTrackerV3')).toBeNull();
            expect(localStorage.getItem('customAIPlatforms')).toBeNull();
            expect(localStorage.getItem('jdModalDismissed')).toBeNull();
            expect(localStorage.getItem('masterPasswordSet')).toBeNull();
            // UI-Settings bleiben
            expect(localStorage.getItem('colorScheme')).toBe('dark');
        });
    });

    describe('clearUserData()', () => {
        test('should clear user data without removing tokens', () => {
            localStorage.setItem(TOKEN_KEY, 'still-here');
            localStorage.setItem('cvData', JSON.stringify({text: 'leak'}));

            Auth.clearUserData();

            expect(localStorage.getItem('cvData')).toBeNull();
            // Token bleibt — clearUserData ist NICHT logout
            expect(localStorage.getItem(TOKEN_KEY)).toBe('still-here');
        });
    });

    describe('refreshToken()', () => {
        test('should use refresh token to get new access token', async () => {
            localStorage.setItem(REFRESH_TOKEN_KEY, 'refresh-456');

            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    access_token: 'new-access-token',
                    token_type: 'Bearer',
                    expires_in: 3600
                })
            });

            const result = await Auth.refreshToken();

            expect(global.fetch).toHaveBeenCalledWith(
                expect.stringContaining('/api/auth/refresh'),
                expect.objectContaining({
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ refresh_token: 'refresh-456' })
                })
            );

            expect(localStorage.getItem(TOKEN_KEY)).toBe('new-access-token');
            expect(result).toEqual({ access_token: 'new-access-token', token_type: 'Bearer', expires_in: 3600 });
        });

        test('should throw error when refresh token missing', async () => {
            await expect(Auth.refreshToken())
                .rejects
                .toThrow();
        });

        test('should throw error on refresh failure', async () => {
            localStorage.setItem(REFRESH_TOKEN_KEY, 'invalid-token');

            global.fetch.mockResolvedValueOnce({
                ok: false,
                json: async () => ({ error: 'Invalid refresh token' })
            });

            await expect(Auth.refreshToken())
                .rejects
                .toThrow('Invalid refresh token');
        });
    });

    describe('fetch()', () => {
        test('should add Authorization header to requests', async () => {
            localStorage.setItem(TOKEN_KEY, 'test-token-123');

            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({ data: 'success' })
            });

            const result = await Auth.fetch('/applications');

            expect(global.fetch).toHaveBeenCalledWith(
                expect.stringContaining('/api/applications'),
                expect.objectContaining({
                    headers: expect.objectContaining({
                        'Authorization': 'Bearer test-token-123'
                    })
                })
            );
            expect(result).toEqual({ data: 'success' });
        });

        test('should auto-refresh token on 401 and retry', async () => {
            localStorage.setItem(TOKEN_KEY, 'expired-token');
            localStorage.setItem(REFRESH_TOKEN_KEY, 'refresh-456');

            // First call returns 401, second returns new token, third succeeds
            global.fetch
                .mockResolvedValueOnce({ status: 401, ok: false })
                .mockResolvedValueOnce({
                    ok: true,
                    json: async () => ({ access_token: 'new-token', token_type: 'Bearer', expires_in: 3600 })
                })
                .mockResolvedValueOnce({
                    ok: true,
                    json: async () => ({ data: 'success' })
                });

            const result = await Auth.fetch('/applications');

            // Should have called fetch 3 times: initial request, refresh, retry
            expect(global.fetch).toHaveBeenCalledTimes(3);
            expect(localStorage.getItem(TOKEN_KEY)).toBe('new-token');
            expect(result).toEqual({ data: 'success' });
        });

        test('should throw error when refresh fails on 401', async () => {
            localStorage.setItem(TOKEN_KEY, 'expired-token');
            localStorage.setItem(REFRESH_TOKEN_KEY, 'invalid-refresh');

            global.fetch
                .mockResolvedValueOnce({ status: 401, ok: false })
                .mockResolvedValueOnce({
                    ok: false,
                    json: async () => ({ error: 'Invalid refresh token' })
                });

            await expect(Auth.fetch('/applications'))
                .rejects
                .toThrow();
        });

        test('should not refresh on non-401 errors', async () => {
            localStorage.setItem(TOKEN_KEY, 'test-token');

            global.fetch.mockResolvedValueOnce({
                ok: false,
                status: 500,
                json: async () => ({ error: 'Server error' })
            });

            await expect(Auth.fetch('/applications'))
                .rejects
                .toThrow();

            // Should only be called once (no refresh attempt)
            expect(global.fetch).toHaveBeenCalledTimes(1);
        });

        test('should throw error when not authenticated', async () => {
            await expect(Auth.fetch('/applications'))
                .rejects
                .toThrow();
        });

        test('should merge custom headers with auth header', async () => {
            localStorage.setItem(TOKEN_KEY, 'test-token-123');

            global.fetch.mockResolvedValueOnce({
                ok: true,
                json: async () => ({ data: 'success' })
            });

            await Auth.fetch('/applications', {
                headers: { 'X-Custom': 'value' }
            });

            expect(global.fetch).toHaveBeenCalledWith(
                expect.stringContaining('/api/applications'),
                expect.objectContaining({
                    headers: expect.objectContaining({
                        'Authorization': 'Bearer test-token-123',
                        'X-Custom': 'value'
                    })
                })
            );
        });
    });

    describe('Error handling', () => {
        test('should handle network errors gracefully', async () => {
            global.fetch.mockRejectedValueOnce(new Error('Network timeout'));

            await expect(Auth.login('test@example.com', 'password'))
                .rejects
                .toThrow('Network timeout');
        });

        test('should parse error messages from API response', async () => {
            global.fetch.mockResolvedValueOnce({
                ok: false,
                json: async () => ({ error: 'Email already in use' })
            });

            await expect(Auth.register('test@example.com', 'password'))
                .rejects
                .toThrow('Email already in use');
        });
    });
});
