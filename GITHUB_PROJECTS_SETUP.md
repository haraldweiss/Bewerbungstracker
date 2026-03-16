# 📊 GitHub Projects Setup Guide

## Overview
This guide helps you create GitHub Projects for each repository to organize and track development work.

## Repositories to Set Up

### 1. Bewerbungstracker
- **Repository**: `haraldweiss/Bewerbungstracker`
- **URL**: https://github.com/haraldweiss/Bewerbungstracker
- **Type**: Public
- **Description**: CV and job application tracking system with AI comparison

### 2. Futurepinballweb
- **Repository**: `haraldweiss/Futurepinballweb`
- **URL**: https://github.com/haraldweiss/Futurepinballweb
- **Type**: Public
- **Description**: Web-based recreation of Futurepinball

### 3. Rulebase Converter
- **Repository**: `haraldweiss/rulebase-converter`
- **URL**: https://github.com/haraldweiss/rulebase-converter
- **Type**: Private
- **Description**: Multi-platform SIEM detection rule converter

## Method 1: Create Projects via GitHub Web UI (Easiest)

### Step 1: Navigate to Your Repository
1. Go to your GitHub repository
2. Click on the **"Projects"** tab at the top
3. Click **"Create a project"** button

### Step 2: Configure Project
1. **Project name**: Enter a clear name
   - Example: "Bewerbungstracker Development"
2. **Description**: Optional, add project details
3. **Template**: Choose a template:
   - **Table**: For task/issue tracking
   - **Board**: For Kanban-style workflow
4. **Visibility**: Set to Public or Private
5. Click **"Create"**

### Step 3: Set Up Views (Optional)
- **Table View**: Default spreadsheet view
- **Board View**: Kanban board (Backlog, In Progress, Done)
- **Roadmap View**: Timeline/milestone view

## Method 2: Create Projects via GitHub CLI

### Prerequisites
```bash
# Update GitHub CLI token with required scopes
gh auth refresh -h github.com -s project,read:project,write:project
```

### Create Projects
```bash
# Bewerbungstracker
gh project create --owner haraldweiss --title "Bewerbungstracker"

# Futurepinballweb
gh project create --owner haraldweiss --title "Futurepinball Web"

# Rulebase Converter
gh project create --owner haraldweiss --title "Rulebase Converter"
```

## Recommended Project Structure

### For Each Project, Create These Fields/Columns:

#### Kanban Board View
```
📋 Backlog
   ├─ New Features
   ├─ Bug Reports
   └─ Documentation

⏳ In Progress
   ├─ Currently Being Worked On
   └─ Pull Requests Open

✅ Done
   ├─ Completed Features
   ├─ Merged PRs
   └─ Released
```

#### Fields to Track
1. **Title** - Issue/PR name
2. **Status** - Backlog/In Progress/In Review/Done
3. **Priority** - Critical/High/Medium/Low
4. **Type** - Feature/Bug/Documentation/Refactor
5. **Assignee** - Team member
6. **Due Date** - Target completion
7. **Labels** - Category tags

## Typical Workflows

### Bewerbungstracker Development
```
Priority Items:
├─ Core Features
│  ├─ CV Comparison with AI (✅ DONE)
│  ├─ File Upload PDF/DOCX (✅ DONE)
│  ├─ Text Cleanup & Validation (✅ DONE)
│  └─ Mobile Optimization
│
├─ Enhancements
│  ├─ Dark/Light Mode (✅ DONE)
│  ├─ Email Integration (✅ DONE)
│  ├─ Database Optimization
│  └─ Performance Tuning
│
└─ Infrastructure
   ├─ Cloud Deployment
   ├─ CI/CD Pipeline
   └─ Automated Testing
```

### Futurepinballweb Development
```
Priority Items:
├─ Game Mechanics
│  ├─ Ball Physics
│  ├─ Flipper Control
│  ├─ Bumper Scoring
│  └─ Ramp Logic
│
├─ UI/UX
│  ├─ Score Display
│  ├─ Game State UI
│  ├─ Mobile Controls
│  └─ Settings Menu
│
└─ Platform Support
   ├─ Browser Compatibility
   ├─ Touch Controls
   ├─ Keyboard Controls
   └─ Mobile Optimization
```

### Rulebase Converter Development
```
Priority Items:
├─ Core Functionality
│  ├─ YARA Parser
│  ├─ Sigma Converter
│  ├─ Splunk SPL Support
│  └─ CloudWatch Support
│
├─ Converters
│  ├─ SIEM Detection Rules
│  ├─ IOC Indicators
│  ├─ Threat Intelligence
│  └─ Log Parsers
│
└─ Testing & Quality
   ├─ Unit Tests
   ├─ Integration Tests
   ├─ Performance Benchmarks
   └─ Documentation
```

## Adding Issues to Projects

### From Repository Issues Tab
1. Go to **Issues** tab
2. Select an issue
3. Click **Projects** panel on right side
4. Add to project and set status

### From Project Board
1. Go to **Projects** tab
2. Click your project
3. Click **+ Add Item**
4. Search for existing issues or create new one

### From Pull Requests
1. Go to **Pull Requests** tab
2. Select a PR
3. Click **Projects** panel
4. Add to project with status

## Project Board Features

### Automation
- Set rules to auto-move cards when:
  - PR is opened → Move to "In Progress"
  - PR is merged → Move to "Done"
  - Issue is closed → Move to "Done"

### Filtering
- View by Status
- View by Priority
- View by Assignee
- View by Due Date
- Custom filters

### Reports (Table View)
- Burndown chart
- Velocity tracking
- Issue aging
- Time estimates

## Best Practices

### 1. Keep Issues Updated
```
✅ Do:
  - Update status regularly
  - Add priority levels
  - Set due dates
  - Assign to team members

❌ Don't:
  - Leave issues in backlog forever
  - Forget to move cards
  - Ignore overdue items
```

### 2. Use Consistent Labels
```
Suggested labels:
- bug: Something isn't working
- enhancement: New feature request
- documentation: Docs need updating
- refactor: Code quality improvement
- urgent: Needs immediate attention
- help wanted: Need community input
- blocked: Waiting on something else
```

### 3. Link Related Items
```
Use in issue descriptions:
- "Fixes #123" - Links to issue
- "Depends on #456" - Shows dependency
- "Related to #789" - Groups related work
```

### 4. Set Milestones
```
Example milestones:
- v1.0 - Initial Release
- v1.1 - Bug Fixes & Polish
- v2.0 - Major Features
- Mobile - Mobile App Version
```

## GitHub Projects API (Advanced)

### Create Project via API
```bash
gh api graphql -f query='
  mutation {
    createProjectV2(input: {
      ownerId: "YOUR_USER_ID"
      title: "Project Name"
    }) {
      projectV2 {
        id
        title
        url
      }
    }
  }
'
```

### Add Issue to Project
```bash
gh api graphql -f query='
  mutation {
    addProjectV2ItemById(input: {
      projectId: "PROJECT_ID"
      contentId: "ISSUE_ID"
    }) {
      item {
        id
      }
    }
  }
'
```

## Troubleshooting

### "Can't create project" error
**Solution**: 
- Check GitHub token has `project` scope
- Update token: `gh auth refresh -s project,read:project,write:project`
- Ensure you have permission to create projects

### "Missing issues in project"
**Solution**:
- Issues must be explicitly added to project
- Go to issue → Add to project via right panel
- Or manually add via project board

### "Project not showing in sidebar"
**Solution**:
- Navigate to Projects tab first
- Refresh page
- Check project visibility settings

## Integration with Development Workflow

### 1. Feature Development
```
Issue → Project → Branch → PR → Review → Merge → Done
```

### 2. Bug Fixes
```
Bug Report → Triage → In Progress → Fix → Test → Merge → Done
```

### 3. Release Planning
```
Backlog → Milestone → In Progress → Release → Done
```

## Monthly Reviews

### Every Month, Review:
- [ ] Completed items count
- [ ] In-progress items (should be <50%)
- [ ] Overdue items (should be 0)
- [ ] Backlog size (should be manageable)
- [ ] Burndown progress
- [ ] Team velocity trends

## Resources

### GitHub Documentation
- [GitHub Projects Documentation](https://docs.github.com/en/issues/planning-and-tracking-with-projects)
- [About Projects](https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects)
- [Quickstart for Projects](https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/quickstart-for-projects)

### GitHub CLI Documentation
- [gh project command](https://cli.github.com/manual/gh_project)
- [GitHub CLI Authentication](https://cli.github.com/manual/gh_auth)

## Next Steps

1. **This Week**: Create all 3 GitHub Projects
2. **Next Week**: Add current issues to projects
3. **Ongoing**: Update project status weekly
4. **Monthly**: Review burndown and velocity
5. **Quarterly**: Plan milestones and releases

---

**Status**: Guide created for manual setup
**Last Updated**: 2026-03-16
**Token Scope Issue**: GitHub CLI needs project scope update for automation
