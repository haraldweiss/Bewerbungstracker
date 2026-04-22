package com.example.bewerbungstracker

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import com.example.bewerbungstracker.data.AppDatabase
import com.example.bewerbungstracker.data.BewerbungstrackerRepository
import com.example.bewerbungstracker.ui.screens.MainTabScreen
import com.example.bewerbungstracker.ui.theme.BewerbungstrackerTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val database = AppDatabase.getInstance(this)
        val repository = BewerbungstrackerRepository(database)
        
        setContent {
            BewerbungstrackerTheme {
                Surface(modifier = Modifier) {
                    MainTabScreen(repository = repository)
                }
            }
        }
    }
}
