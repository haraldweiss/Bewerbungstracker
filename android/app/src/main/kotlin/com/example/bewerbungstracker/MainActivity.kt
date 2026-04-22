package com.example.bewerbungstracker

import android.content.Context
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.example.bewerbungstracker.data.AppDatabase
import com.example.bewerbungstracker.data.BewerbungstrackerRepository
import com.example.bewerbungstracker.ui.screens.MainTabScreen
import com.example.bewerbungstracker.ui.theme.BewerbungstrackerTheme
import kotlinx.coroutines.flow.map

private val PREFERENCES_NAME = "settings"
private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = PREFERENCES_NAME)
private val APPEARANCE_MODE_KEY = stringPreferencesKey("appearance_mode")

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val database = AppDatabase.getInstance(this)
        val repository = BewerbungstrackerRepository(database)

        setContent {
            // Read appearance mode preference from DataStore
            val appearanceMode by this@MainActivity.dataStore.data
                .map { preferences ->
                    preferences[APPEARANCE_MODE_KEY] ?: "system"
                }
                .collectAsState(initial = "system")

            // Determine dark theme based on appearance mode preference
            val darkTheme = when (appearanceMode) {
                "light" -> false
                "dark" -> true
                else -> isSystemInDarkTheme()  // "system" - use device setting
            }

            BewerbungstrackerTheme(darkTheme = darkTheme) {
                Surface(modifier = Modifier) {
                    MainTabScreen(repository = repository)
                }
            }
        }
    }
}
