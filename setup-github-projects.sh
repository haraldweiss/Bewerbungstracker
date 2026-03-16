#!/bin/bash

# GitHub Projects Setup Script
# This script creates GitHub Projects for your repositories

echo "🚀 GitHub Projects Setup Script"
echo "================================"
echo ""

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo "❌ GitHub CLI (gh) not found!"
    echo "Install it from: https://cli.github.com"
    exit 1
fi

# Check authentication
if ! gh auth status &> /dev/null; then
    echo "❌ Not authenticated with GitHub!"
    echo "Run: gh auth login"
    exit 1
fi

echo "✅ GitHub CLI authenticated"
echo ""

# Update token scopes (if needed)
echo "📋 Updating GitHub token scopes..."
gh auth refresh -h github.com -s project,read:project,write:project 2>/dev/null || true

echo ""
echo "Creating GitHub Projects..."
echo ""

# Array of projects to create
declare -a projects=(
    "Bewerbungstracker|CV and job application tracking system with AI comparison"
    "Futurepinball Web|Web-based recreation of Futurepinball game"
    "Rulebase Converter|Multi-platform SIEM detection rule converter"
)

# Create each project
for project in "${projects[@]}"; do
    IFS='|' read -r title description <<< "$project"
    
    echo "📊 Creating project: $title"
    echo "   Description: $description"
    
    # Attempt to create project
    result=$(gh project create --owner haraldweiss --title "$title" --format json 2>&1)
    
    if echo "$result" | grep -q "error"; then
        echo "⚠️  Error creating project: $title"
        echo "   Reason: $(echo $result | grep -o 'error: [^}]*' | head -1)"
        echo ""
        echo "💡 To create projects manually:"
        echo "   1. Visit: https://github.com/haraldweiss?tab=projects"
        echo "   2. Click 'Create a project' button"
        echo "   3. Enter title: $title"
        echo "   4. Add description: $description"
        echo "   5. Choose template: 'Table' or 'Board'"
        echo ""
    else
        echo "✅ Project created successfully!"
        echo ""
    fi
done

echo "================================"
echo "📝 Setup Complete!"
echo ""
echo "Next steps:"
echo "1. Visit https://github.com/haraldweiss?tab=projects"
echo "2. Configure each project with desired views (Table, Board, Roadmap)"
echo "3. Add existing issues to projects"
echo "4. Set up automation rules (optional)"
echo ""
echo "For detailed setup guide, see: GITHUB_PROJECTS_SETUP.md"
