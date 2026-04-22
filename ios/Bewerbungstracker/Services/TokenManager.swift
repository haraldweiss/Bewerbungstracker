import Foundation
import Security

/// Secure token management using Keychain
final class TokenManager {
    static let shared = TokenManager()

    private let keychainService = "com.bewerbungstracker.app"
    private let accessTokenKey = "accessToken"
    private let refreshTokenKey = "refreshToken"
    private let expiryKey = "accessTokenExpiry"

    private init() {}

    // MARK: - Token Storage

    /// Store access token in Keychain
    /// - Parameters:
    ///   - token: JWT access token
    ///   - expiresIn: Token expiry duration in seconds
    func storeAccessToken(_ token: String, expiresIn: Int) {
        let expiryDate = Date().addingTimeInterval(TimeInterval(expiresIn))
        storeInKeychain(token, for: accessTokenKey)
        UserDefaults.standard.set(expiryDate, forKey: expiryKey)
    }

    /// Store refresh token in Keychain
    /// - Parameter token: JWT refresh token
    func storeRefreshToken(_ token: String) {
        storeInKeychain(token, for: refreshTokenKey)
    }

    /// Retrieve access token from Keychain
    /// - Returns: Access token or nil if not found/expired
    func getAccessToken() -> String? {
        // Check if token is expired
        if let expiryDate = UserDefaults.standard.object(forKey: expiryKey) as? Date {
            if Date() > expiryDate {
                // Token expired, attempt refresh
                return nil
            }
        }

        return retrieveFromKeychain(for: accessTokenKey)
    }

    /// Retrieve refresh token from Keychain
    /// - Returns: Refresh token or nil if not found
    func getRefreshToken() -> String? {
        retrieveFromKeychain(for: refreshTokenKey)
    }

    /// Check if access token exists and is valid
    /// - Returns: true if valid token exists
    var hasValidToken: Bool {
        guard let expiryDate = UserDefaults.standard.object(forKey: expiryKey) as? Date else {
            return false
        }
        return Date() < expiryDate
    }

    /// Clear all stored tokens
    func clearTokens() {
        deleteFromKeychain(for: accessTokenKey)
        deleteFromKeychain(for: refreshTokenKey)
        UserDefaults.standard.removeObject(forKey: expiryKey)
    }

    // MARK: - Keychain Operations

    private func storeInKeychain(_ value: String, for key: String) {
        // Delete existing value first
        deleteFromKeychain(for: key)

        guard let data = value.data(using: .utf8) else {
            return
        }

        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: keychainService,
            kSecAttrAccount as String: key,
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly
        ]

        SecItemAdd(query as CFDictionary, nil)
    }

    private func retrieveFromKeychain(for key: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: keychainService,
            kSecAttrAccount as String: key,
            kSecReturnData as String: true
        ]

        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)

        guard status == errSecSuccess,
              let data = result as? Data,
              let string = String(data: data, encoding: .utf8)
        else {
            return nil
        }

        return string
    }

    private func deleteFromKeychain(for key: String) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: keychainService,
            kSecAttrAccount as String: key
        ]

        SecItemDelete(query as CFDictionary)
    }

    // MARK: - Token Refresh

    /// Refresh access token using refresh token
    /// - Returns: New access token or nil if refresh fails
    func refreshAccessToken() async -> String? {
        guard let refreshToken = getRefreshToken() else {
            return nil
        }

        do {
            let url = URL(string: "http://localhost:8080/api/auth/refresh")!
            var request = URLRequest(url: url)
            request.httpMethod = "POST"
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")

            let body = ["refresh_token": refreshToken]
            request.httpBody = try JSONEncoder().encode(body)

            let (data, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse, (200...299).contains(httpResponse.statusCode) else {
                clearTokens()
                return nil
            }

            let authResponse = try JSONDecoder().decode(AuthResponse.self, from: data)
            storeAccessToken(authResponse.accessToken, expiresIn: authResponse.expiresIn)

            return authResponse.accessToken
        } catch {
            clearTokens()
            return nil
        }
    }

    // MARK: - Token Decoding (optional, for debugging)

    /// Decode JWT token payload (without verification)
    /// - Parameter token: JWT token to decode
    /// - Returns: Decoded payload dictionary or nil
    func decodeToken(_ token: String) -> [String: Any]? {
        let components = token.split(separator: ".")
        guard components.count == 3 else {
            return nil
        }

        var padding = String(components[1])
        while padding.count % 4 != 0 {
            padding.append("=")
        }

        guard let data = Data(base64Encoded: padding),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else {
            return nil
        }

        return json
    }
}

// MARK: - Response Model (imported from APIClient for convenience)

extension TokenManager {
    struct AuthResponse: Codable {
        let accessToken: String
        let refreshToken: String
        let tokenType: String
        let expiresIn: Int

        enum CodingKeys: String, CodingKey {
            case accessToken = "access_token"
            case refreshToken = "refresh_token"
            case tokenType = "token_type"
            case expiresIn = "expires_in"
        }
    }
}
