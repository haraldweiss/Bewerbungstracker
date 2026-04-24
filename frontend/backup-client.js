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
        try {
            const response = await Auth.fetch(`${this.baseUrl}/list`, {
                method: 'GET'
            });
            if (!response.ok) {
                throw new Error(`Failed to list backups: ${response.status}`);
            }
            const data = await response.json();
            return data.backups || [];
        } catch (error) {
            console.error('Error listing backups:', error);
            throw error;
        }
    }

    /**
     * Export current user data in JSON or CSV format
     * @param {string} format - 'json' or 'csv'
     * @param {boolean} includeEmails - Include emails in export
     * @returns {Promise<Blob>} File blob for download
     */
    async exportData(format = 'json', includeEmails = true) {
        try {
            const url = new URL(`${window.location.origin}${this.baseUrl}/export`);
            url.searchParams.append('format', format);
            url.searchParams.append('include_emails', includeEmails);

            const response = await Auth.fetch(url.toString(), {
                method: 'GET'
            });

            if (!response.ok) {
                throw new Error(`Export failed: ${response.status}`);
            }

            return await response.blob();
        } catch (error) {
            console.error('Error exporting data:', error);
            throw error;
        }
    }

    /**
     * Get specific backup version
     * @param {number} version - Backup version number
     * @param {boolean} decrypt - Decrypt the backup data
     * @returns {Promise<Object>} Backup object with data
     */
    async getBackup(version, decrypt = true) {
        try {
            const url = new URL(`${window.location.origin}${this.baseUrl}/${version}`);
            url.searchParams.append('decrypt', decrypt);

            const response = await Auth.fetch(url.toString(), {
                method: 'GET'
            });

            if (!response.ok) {
                throw new Error(`Failed to get backup: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Error getting backup:', error);
            throw error;
        }
    }

    /**
     * Restore from specific backup version
     * @param {number} version - Backup version to restore from
     * @param {boolean} clearExisting - Clear existing data before restore
     * @returns {Promise<Object>} Restore result with summary
     */
    async restoreBackup(version, clearExisting = false) {
        try {
            const response = await Auth.fetch(`${this.baseUrl}/${version}/restore`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    confirm: true,
                    clear_existing: clearExisting
                })
            });

            if (!response.ok) {
                throw new Error(`Restore failed: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Error restoring backup:', error);
            throw error;
        }
    }

    /**
     * Import backup from file
     * @param {File} file - JSON backup file
     * @returns {Promise<Object>} Import result with summary
     */
    async importBackup(file) {
        try {
            const formData = new FormData();
            formData.append('file', file);

            const response = await Auth.fetch(`${this.baseUrl}/import`, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(`Import failed: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Error importing backup:', error);
            throw error;
        }
    }

    /**
     * Download exported file
     * @param {string} format - 'json' or 'csv'
     * @param {string} filename - Name for downloaded file
     */
    async downloadExport(format = 'json', filename = null) {
        try {
            const blob = await this.exportData(format, true);
            const defaultFilename = filename || `backup_${new Date().toISOString().split('T')[0]}.${format}`;
            this._downloadBlob(blob, defaultFilename);
        } catch (error) {
            console.error('Error downloading export:', error);
            throw error;
        }
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
