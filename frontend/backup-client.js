/**
 * Backup API Client
 * Handles all backup-related API calls: export, import, list, restore
 */

class BackupClient {
    constructor() {
        this.baseUrl = '/api/backup';
    }

    /**
     * List all backups for current user
     * @returns {Promise<Array>} Array of backup objects with version, created_at, type, summary
     */
    async listBackups() {
        const data = await Auth.fetch(`${this.baseUrl}/list`, {
            method: 'GET'
        });
        // Auth.fetch already parses JSON and throws on errors
        return data.backups || [];
    }

    /**
     * Export current user data in JSON or CSV format
     * @param {string} format - 'json' or 'csv'
     * @param {boolean} includeEmails - Include emails in export
     * @returns {Promise<Blob>} File blob for download
     */
    async exportData(format = 'json', includeEmails = true) {
        // Note: For binary responses, we need to use native fetch with Bearer token
        const token = Auth.getToken();
        if (!token) {
            throw new Error('Not authenticated');
        }

        const url = new URL(`${window.location.origin}${this.baseUrl}/export`);
        url.searchParams.append('format', format);
        url.searchParams.append('include_emails', includeEmails);

        const response = await fetch(url.toString(), {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });

        if (!response.ok) {
            throw new Error(`Export failed: ${response.status}`);
        }

        return await response.blob();
    }

    /**
     * Get specific backup version
     * @param {number} version - Backup version number
     * @param {boolean} decrypt - Decrypt the backup data
     * @returns {Promise<Object>} Backup object with data
     */
    async getBackup(version, decrypt = true) {
        const url = `/backup/${version}?decrypt=${decrypt}`;
        const data = await Auth.fetch(url, {
            method: 'GET'
        });
        // Auth.fetch already parses JSON and throws on errors
        return data;
    }

    /**
     * Restore from specific backup version
     * @param {number} version - Backup version to restore from
     * @param {boolean} clearExisting - Clear existing data before restore
     * @returns {Promise<Object>} Restore result with summary
     */
    async restoreBackup(version, clearExisting = false) {
        const data = await Auth.fetch(`/backup/${version}/restore`, {
            method: 'POST',
            body: JSON.stringify({
                confirm: true,
                clear_existing: clearExisting
            })
        });
        // Auth.fetch already parses JSON and throws on errors
        return data;
    }

    /**
     * Import backup from file
     * @param {File} file - JSON backup file
     * @returns {Promise<Object>} Import result with summary
     */
    async importBackup(file) {
        // For multipart form data, use native fetch with Bearer token
        const token = Auth.getToken();
        if (!token) {
            throw new Error('Not authenticated');
        }

        const formData = new FormData();
        formData.append('backup', file);

        const url = `${window.location.origin}${this.baseUrl}/import`;
        console.log('Importing backup:', { url, fileName: file.name, fileSize: file.size });

        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            },
            body: formData
        });

        console.log('Import response:', { status: response.status, ok: response.ok });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            console.error('Import error response:', errorData);
            throw new Error(`Import failed: ${response.status} - ${errorData.error || 'Unknown error'}`);
        }

        return await response.json();
    }

    /**
     * Download exported file
     * @param {string} format - 'json' or 'csv'
     * @param {string} filename - Name for downloaded file
     */
    async downloadExport(format = 'json', filename = null) {
        const blob = await this.exportData(format, true);
        const defaultFilename = filename || `backup_${new Date().toISOString().split('T')[0]}.${format}`;
        this._downloadBlob(blob, defaultFilename);
    }

    /**
     * Helper method to download blob as file
     * @private
     * @param {Blob} blob - File blob
     * @param {string} filename - Download filename
     */
    _downloadBlob(blob, filename) {
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    }
}

// Create global instance
const backupClient = new BackupClient();
