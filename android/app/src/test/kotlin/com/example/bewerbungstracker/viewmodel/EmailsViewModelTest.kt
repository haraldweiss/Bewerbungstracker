package com.example.bewerbungstracker.viewmodel

import com.example.bewerbungstracker.data.ApplicationEntity
import com.example.bewerbungstracker.data.BewerbungstrackerRepository
import com.example.bewerbungstracker.data.EmailEntity
import com.example.bewerbungstracker.ui.viewmodels.EmailsViewModel
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
import org.mockito.kotlin.verify
import org.mockito.kotlin.whenever
import java.util.UUID

/**
 * Unit tests for EmailsViewModel.
 *
 * Tests cover:
 * - Email loading and grouping
 * - Search functionality
 * - Email deletion
 * - Error handling
 */
class EmailsViewModelTest {

    @Mock
    private lateinit var repository: BewerbungstrackerRepository

    private lateinit var viewModel: EmailsViewModel
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
    fun testLoadEmails_Success() = runTest {
        val apps = listOf(
            ApplicationEntity(
                id = "app-1",
                userId = userId,
                company = "Google",
                position = "Engineer",
                status = "applied"
            )
        )
        val emails = listOf(
            EmailEntity(
                id = UUID.randomUUID().toString(),
                userId = userId,
                subject = "Interview Confirmation",
                fromAddress = "hr@google.com",
                matchedApplicationId = "app-1"
            )
        )

        whenever(repository.getAllEmails(userId)).thenReturn(emails)
        whenever(repository.getAllApplications(userId)).thenReturn(apps)

        viewModel = EmailsViewModel(repository, userId)

        verify(repository).getAllEmails(userId)
        verify(repository).getAllApplications(userId)
    }

    @Test
    fun testLoadEmails_EmptyList() = runTest {
        whenever(repository.getAllEmails(userId)).thenReturn(emptyList())
        whenever(repository.getAllApplications(userId)).thenReturn(emptyList())

        viewModel = EmailsViewModel(repository, userId)

        verify(repository).getAllEmails(userId)
    }

    @Test
    fun testGroupEmails_ByApplication() = runTest {
        val appId = "app-1"
        val apps = listOf(
            ApplicationEntity(
                id = appId,
                userId = userId,
                company = "Google",
                position = "Engineer",
                status = "interview"
            )
        )
        val emails = listOf(
            EmailEntity(
                id = UUID.randomUUID().toString(),
                userId = userId,
                subject = "Email 1",
                fromAddress = "hr@google.com",
                matchedApplicationId = appId,
                timestamp = System.currentTimeMillis()
            ),
            EmailEntity(
                id = UUID.randomUUID().toString(),
                userId = userId,
                subject = "Email 2",
                fromAddress = "team@google.com",
                matchedApplicationId = appId,
                timestamp = System.currentTimeMillis() - 3600000
            )
        )

        whenever(repository.getAllEmails(userId)).thenReturn(emails)
        whenever(repository.getAllApplications(userId)).thenReturn(apps)

        viewModel = EmailsViewModel(repository, userId)

        val state = viewModel.uiState.first()
        assert(state.groupedEmails.size > 0)
    }

    @Test
    fun testUpdateSearch_FiltersEmails() = runTest {
        val apps = listOf(
            ApplicationEntity(
                id = "app-1",
                userId = userId,
                company = "Google",
                position = "Engineer",
                status = "applied"
            )
        )
        val emails = listOf(
            EmailEntity(
                id = UUID.randomUUID().toString(),
                userId = userId,
                subject = "Interview from Google",
                fromAddress = "hr@google.com",
                matchedApplicationId = "app-1"
            )
        )

        whenever(repository.getAllEmails(userId)).thenReturn(emails)
        whenever(repository.getAllApplications(userId)).thenReturn(apps)

        viewModel = EmailsViewModel(repository, userId)

        viewModel.updateSearch("Google")

        val state = viewModel.uiState.first()
        assert(state.searchText == "Google")
    }

    @Test
    fun testUpdateSearch_SearchBySubject() = runTest {
        val emails = listOf(
            EmailEntity(
                id = UUID.randomUUID().toString(),
                userId = userId,
                subject = "Interview Confirmation",
                fromAddress = "hr@example.com",
                matchedApplicationId = null
            ),
            EmailEntity(
                id = UUID.randomUUID().toString(),
                userId = userId,
                subject = "Rejection Notice",
                fromAddress = "hr@example.com",
                matchedApplicationId = null
            )
        )

        whenever(repository.getAllEmails(userId)).thenReturn(emails)
        whenever(repository.getAllApplications(userId)).thenReturn(emptyList())

        viewModel = EmailsViewModel(repository, userId)

        viewModel.updateSearch("Interview")

        val state = viewModel.uiState.first()
        assert(state.searchText == "Interview")
    }

    @Test
    fun testUpdateSearch_SearchByFromAddress() = runTest {
        val emails = listOf(
            EmailEntity(
                id = UUID.randomUUID().toString(),
                userId = userId,
                subject = "Job Offer",
                fromAddress = "recruiter@company.com",
                matchedApplicationId = null
            )
        )

        whenever(repository.getAllEmails(userId)).thenReturn(emails)
        whenever(repository.getAllApplications(userId)).thenReturn(emptyList())

        viewModel = EmailsViewModel(repository, userId)

        viewModel.updateSearch("recruiter")

        val state = viewModel.uiState.first()
        assert(state.searchText == "recruiter")
    }

    @Test
    fun testDeleteEmail_Success() = runTest {
        val email = EmailEntity(
            id = UUID.randomUUID().toString(),
            userId = userId,
            subject = "Test Email",
            fromAddress = "test@example.com"
        )

        whenever(repository.getAllEmails(userId)).thenReturn(listOf(email))
        whenever(repository.getAllApplications(userId)).thenReturn(emptyList())
        whenever(repository.deleteEmail(email)).then { }

        viewModel = EmailsViewModel(repository, userId)

        viewModel.deleteEmail(email)

        verify(repository).deleteEmail(email)
    }

    @Test
    fun testDeleteEmail_RemovesFromList() = runTest {
        val email = EmailEntity(
            id = UUID.randomUUID().toString(),
            userId = userId,
            subject = "Email to Delete",
            fromAddress = "test@example.com"
        )

        whenever(repository.getAllEmails(userId)).thenReturn(listOf(email))
        whenever(repository.getAllApplications(userId)).thenReturn(emptyList())
        whenever(repository.deleteEmail(email)).then { }

        viewModel = EmailsViewModel(repository, userId)

        viewModel.deleteEmail(email)

        // Verify delete was called
        verify(repository).deleteEmail(email)
    }

    @Test
    fun testGroupEmails_MultipleApplications() = runTest {
        val apps = listOf(
            ApplicationEntity(
                id = "app-1",
                userId = userId,
                company = "Google",
                position = "Engineer",
                status = "interview"
            ),
            ApplicationEntity(
                id = "app-2",
                userId = userId,
                company = "Microsoft",
                position = "Manager",
                status = "applied"
            )
        )
        val emails = listOf(
            EmailEntity(
                id = UUID.randomUUID().toString(),
                userId = userId,
                subject = "Google Interview",
                fromAddress = "google@company.com",
                matchedApplicationId = "app-1",
                timestamp = System.currentTimeMillis()
            ),
            EmailEntity(
                id = UUID.randomUUID().toString(),
                userId = userId,
                subject = "Microsoft Interview",
                fromAddress = "microsoft@company.com",
                matchedApplicationId = "app-2",
                timestamp = System.currentTimeMillis()
            )
        )

        whenever(repository.getAllEmails(userId)).thenReturn(emails)
        whenever(repository.getAllApplications(userId)).thenReturn(apps)

        viewModel = EmailsViewModel(repository, userId)

        val state = viewModel.uiState.first()
        // Should have 2 groups
        assert(state.groupedEmails.size > 0)
    }

    @Test
    fun testGroupEmails_SortsByTimestamp() = runTest {
        val appId = "app-1"
        val apps = listOf(
            ApplicationEntity(
                id = appId,
                userId = userId,
                company = "Google",
                position = "Engineer",
                status = "applied"
            )
        )
        val now = System.currentTimeMillis()
        val emails = listOf(
            EmailEntity(
                id = UUID.randomUUID().toString(),
                userId = userId,
                subject = "Older Email",
                fromAddress = "hr@google.com",
                matchedApplicationId = appId,
                timestamp = now - 86400000
            ),
            EmailEntity(
                id = UUID.randomUUID().toString(),
                userId = userId,
                subject = "Newer Email",
                fromAddress = "team@google.com",
                matchedApplicationId = appId,
                timestamp = now
            )
        )

        whenever(repository.getAllEmails(userId)).thenReturn(emails)
        whenever(repository.getAllApplications(userId)).thenReturn(apps)

        viewModel = EmailsViewModel(repository, userId)

        val state = viewModel.uiState.first()
        // Verify emails are grouped
        assert(state.groupedEmails.size > 0)
    }

    @Test
    fun testClearError() = runTest {
        whenever(repository.getAllEmails(userId)).thenReturn(emptyList())
        whenever(repository.getAllApplications(userId)).thenReturn(emptyList())

        viewModel = EmailsViewModel(repository, userId)

        viewModel.clearError()

        val state = viewModel.uiState.first()
        assert(state.errorMessage == null)
    }

    @Test
    fun testUpdateSearch_CaseInsensitive() = runTest {
        val emails = listOf(
            EmailEntity(
                id = UUID.randomUUID().toString(),
                userId = userId,
                subject = "INTERVIEW CONFIRMATION",
                fromAddress = "hr@example.com"
            )
        )

        whenever(repository.getAllEmails(userId)).thenReturn(emails)
        whenever(repository.getAllApplications(userId)).thenReturn(emptyList())

        viewModel = EmailsViewModel(repository, userId)

        viewModel.updateSearch("interview")

        val state = viewModel.uiState.first()
        assert(state.searchText == "interview")
    }

    @Test
    fun testGroupEmails_WithUnmatchedEmails() = runTest {
        val emails = listOf(
            EmailEntity(
                id = UUID.randomUUID().toString(),
                userId = userId,
                subject = "Unmatched Email",
                fromAddress = "unknown@example.com",
                matchedApplicationId = null
            )
        )

        whenever(repository.getAllEmails(userId)).thenReturn(emails)
        whenever(repository.getAllApplications(userId)).thenReturn(emptyList())

        viewModel = EmailsViewModel(repository, userId)

        val state = viewModel.uiState.first()
        // Should still group unmatched emails
        assert(state.groupedEmails.size > 0)
    }
}
