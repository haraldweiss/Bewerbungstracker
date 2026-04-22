package com.example.bewerbungstracker.viewmodel

import androidx.lifecycle.viewModelScope
import com.example.bewerbungstracker.data.ApplicationEntity
import com.example.bewerbungstracker.data.BewerbungstrackerRepository
import com.example.bewerbungstracker.ui.viewmodels.ApplicationsViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Before
import org.junit.Test
import org.mockito.Mock
import org.mockito.MockitoAnnotations
import org.mockito.kotlin.any
import org.mockito.kotlin.never
import org.mockito.kotlin.verify
import org.mockito.kotlin.whenever
import java.util.UUID

/**
 * Unit tests for ApplicationsViewModel.
 *
 * Tests cover:
 * - CRUD operations (create, read, update, delete)
 * - Filter/search state management
 * - Error handling
 */
class ApplicationsViewModelTest {

    @Mock
    private lateinit var repository: BewerbungstrackerRepository

    private lateinit var viewModel: ApplicationsViewModel
    private val testDispatcher = StandardTestDispatcher()
    private val userId = "test-user"

    @Before
    fun setUp() {
        MockitoAnnotations.openMocks(this)
        Dispatchers.setMain(testDispatcher)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun testLoadApplications_Success() = runTest {
        val apps = listOf(
            ApplicationEntity(
                id = UUID.randomUUID().toString(),
                userId = userId,
                company = "Google",
                position = "Engineer",
                status = "applied"
            ),
            ApplicationEntity(
                id = UUID.randomUUID().toString(),
                userId = userId,
                company = "Microsoft",
                position = "Manager",
                status = "interview"
            )
        )

        whenever(repository.getAllApplications(userId)).thenReturn(apps)

        viewModel = ApplicationsViewModel(repository, userId)

        verify(repository).getAllApplications(userId)
    }

    @Test
    fun testLoadApplications_EmptyList() = runTest {
        whenever(repository.getAllApplications(userId)).thenReturn(emptyList())

        viewModel = ApplicationsViewModel(repository, userId)

        verify(repository).getAllApplications(userId)
    }

    @Test
    fun testUpdateSearch_FiltersApplications() = runTest {
        val apps = listOf(
            ApplicationEntity(
                id = UUID.randomUUID().toString(),
                userId = userId,
                company = "Google",
                position = "Engineer",
                status = "applied"
            ),
            ApplicationEntity(
                id = UUID.randomUUID().toString(),
                userId = userId,
                company = "Microsoft",
                position = "Manager",
                status = "interview"
            )
        )

        whenever(repository.getAllApplications(userId)).thenReturn(apps)

        viewModel = ApplicationsViewModel(repository, userId)

        viewModel.updateSearch("Google")

        // Verify state is updated with search text
        val state = viewModel.uiState.first()
        assert(state.searchText == "Google")
    }

    @Test
    fun testUpdateSearch_CasInsensitive() = runTest {
        val apps = listOf(
            ApplicationEntity(
                id = UUID.randomUUID().toString(),
                userId = userId,
                company = "Google",
                position = "Engineer",
                status = "applied"
            )
        )

        whenever(repository.getAllApplications(userId)).thenReturn(apps)

        viewModel = ApplicationsViewModel(repository, userId)

        viewModel.updateSearch("google")

        val state = viewModel.uiState.first()
        assert(state.searchText == "google")
    }

    @Test
    fun testSetSelectedFilter_UpdatesFilter() = runTest {
        whenever(repository.getAllApplications(userId)).thenReturn(emptyList())

        viewModel = ApplicationsViewModel(repository, userId)

        viewModel.setSelectedFilter("interview")

        val state = viewModel.uiState.first()
        assert(state.selectedFilter == "interview")
    }

    @Test
    fun testSetSelectedFilter_AllFilter() = runTest {
        whenever(repository.getAllApplications(userId)).thenReturn(emptyList())

        viewModel = ApplicationsViewModel(repository, userId)

        viewModel.setSelectedFilter("all")

        val state = viewModel.uiState.first()
        assert(state.selectedFilter == "all")
    }

    @Test
    fun testCreateApplication_Success() = runTest {
        whenever(repository.getAllApplications(userId)).thenReturn(emptyList())
        whenever(repository.insertApplication(any())).then { }

        viewModel = ApplicationsViewModel(repository, userId)

        viewModel.createApplication("NewCorp", "Developer")

        verify(repository).insertApplication(any())
    }

    @Test
    fun testCreateApplication_WithDate() = runTest {
        whenever(repository.getAllApplications(userId)).thenReturn(emptyList())
        whenever(repository.insertApplication(any())).then { }

        viewModel = ApplicationsViewModel(repository, userId)

        val appliedDate = System.currentTimeMillis() - 86400000
        viewModel.createApplication("NewCorp", "Developer", appliedDate)

        verify(repository).insertApplication(any())
    }

    @Test
    fun testUpdateApplication_Success() = runTest {
        val app = ApplicationEntity(
            id = UUID.randomUUID().toString(),
            userId = userId,
            company = "Google",
            position = "Engineer",
            status = "applied"
        )

        whenever(repository.getAllApplications(userId)).thenReturn(listOf(app))
        whenever(repository.updateApplication(any())).then { }

        viewModel = ApplicationsViewModel(repository, userId)

        viewModel.updateApplication(app.copy(status = "interview"))

        verify(repository).updateApplication(any())
    }

    @Test
    fun testDeleteApplication_Success() = runTest {
        val app = ApplicationEntity(
            id = UUID.randomUUID().toString(),
            userId = userId,
            company = "Google",
            position = "Engineer",
            status = "applied"
        )

        whenever(repository.getAllApplications(userId)).thenReturn(listOf(app))
        whenever(repository.deleteApplication(app)).then { }

        viewModel = ApplicationsViewModel(repository, userId)

        viewModel.deleteApplication(app)

        verify(repository).deleteApplication(app)
    }

    @Test
    fun testFilter_AppliedStatus() = runTest {
        val apps = listOf(
            ApplicationEntity(
                id = UUID.randomUUID().toString(),
                userId = userId,
                company = "Google",
                position = "Engineer",
                status = "applied"
            ),
            ApplicationEntity(
                id = UUID.randomUUID().toString(),
                userId = userId,
                company = "Microsoft",
                position = "Manager",
                status = "interview"
            )
        )

        whenever(repository.getAllApplications(userId)).thenReturn(apps)

        viewModel = ApplicationsViewModel(repository, userId)

        viewModel.setSelectedFilter("applied")

        val state = viewModel.uiState.first()
        assert(state.selectedFilter == "applied")
    }

    @Test
    fun testFilter_InterviewStatus() = runTest {
        val apps = listOf(
            ApplicationEntity(
                id = UUID.randomUUID().toString(),
                userId = userId,
                company = "Google",
                position = "Engineer",
                status = "applied"
            ),
            ApplicationEntity(
                id = UUID.randomUUID().toString(),
                userId = userId,
                company = "Microsoft",
                position = "Manager",
                status = "interview"
            )
        )

        whenever(repository.getAllApplications(userId)).thenReturn(apps)

        viewModel = ApplicationsViewModel(repository, userId)

        viewModel.setSelectedFilter("interview")

        val state = viewModel.uiState.first()
        assert(state.selectedFilter == "interview")
    }

    @Test
    fun testFilter_OfferStatus() = runTest {
        val apps = listOf(
            ApplicationEntity(
                id = UUID.randomUUID().toString(),
                userId = userId,
                company = "Google",
                position = "Engineer",
                status = "offer"
            )
        )

        whenever(repository.getAllApplications(userId)).thenReturn(apps)

        viewModel = ApplicationsViewModel(repository, userId)

        viewModel.setSelectedFilter("offer")

        val state = viewModel.uiState.first()
        assert(state.selectedFilter == "offer")
    }

    @Test
    fun testClearError() = runTest {
        whenever(repository.getAllApplications(userId)).thenReturn(emptyList())

        viewModel = ApplicationsViewModel(repository, userId)

        viewModel.clearError()

        val state = viewModel.uiState.first()
        assert(state.errorMessage == null)
    }

    @Test
    fun testSetShowCreateDialog_True() = runTest {
        whenever(repository.getAllApplications(userId)).thenReturn(emptyList())

        viewModel = ApplicationsViewModel(repository, userId)

        viewModel.setShowCreateDialog(true)

        val state = viewModel.uiState.first()
        assert(state.showCreateDialog)
    }

    @Test
    fun testSetShowCreateDialog_False() = runTest {
        whenever(repository.getAllApplications(userId)).thenReturn(emptyList())

        viewModel = ApplicationsViewModel(repository, userId)

        viewModel.setShowCreateDialog(false)

        val state = viewModel.uiState.first()
        assert(!state.showCreateDialog)
    }
}
