# Question Bank Management Guide

This guide provides step-by-step instructions for managing questions in your CMS Question Bank system.

## 🔍 Current Status Analysis

Based on our analysis, your question bank contains:
- **Total Questions**: 2004
- **2018**: 235 questions ✅
- **2019**: 243 questions ✅  
- **2020**: 257 questions ✅

**Key Findings**:
- All years 2018-2020 have adequate questions in the database
- **Issue is likely in frontend filtering or display logic**
- 94.7% of questions lack topics (affects categorization)
- 90.0% of questions lack explanations (affects learning value)

## 🛠️ Step-by-Step Question Management

### 1. Adding a New Question Manually

#### Via Django Admin (Recommended)
1. **Access Admin Panel**:
   - Go to `http://localhost:8000/admin/`
   - Login with your admin credentials

2. **Navigate to Questions**:
   - Click on "Questions" under "QUESTIONS" section

3. **Add New Question**:
   - Click "Add question" button
   - Fill in the required fields:
     ```
     Question Text*: The actual question
     Option A*: First option
     Option B*: Second option  
     Option C*: Third option
     Option D*: Fourth option
     Correct Answer*: A, B, C, or D
     Year*: Exam year (e.g., 2020)
     Subject*: Select from dropdown
     Topic*: Select appropriate topic (optional but recommended)
     Difficulty: Easy/Medium/Hard
     ```

4. **Add Explanations (Important)**:
   ```
   Explanation: Detailed answer explanation
   Concept Explanation: From-basics explanation
     Mnemonic: Memory trick or shortcut
     Book Name: Reference textbook
     Chapter: Chapter number/name
     Page Number: Page reference
     ```

5. **Save**:
   - Click "Save" to create the question
   - Review the question appears correctly

#### Via Management Command
```bash
# Add single question (advanced)
python manage.py shell
```
```python
from questions.models import Question, Subject, Subject

# Get subject
subject = Subject.objects.get(name='General Medicine')

# Create question
question = Question.objects.create(
    question_text="What is the most common cause of acute myocardial infarction?",
    option_a="Coronary artery thrombosis",
    option_b="Coronary artery spasm", 
    option_c="Aortic dissection",
    option_d="Coronary artery embolism",
    correct_answer="A",
    year=2023,
    subject=subject,
    difficulty="medium",
    explanation="Coronary artery thrombosis due to plaque rupture is the most common cause..."
)
```

### 2. Editing an Existing Question

#### Via Django Admin
1. **Find the Question**:
   - Go to Admin → Questions
   - Use search or filter by year/subject
   - Click on the question ID to edit

2. **Make Changes**:
   - Edit any field as needed
   - For multiple choice questions, ensure options are clear
   - Update explanation if changing answer

3. **Save Changes**:
   - Click "Save" to apply changes
   - Verify the question displays correctly

#### Via Management Command
```bash
python manage.py shell
```
```python
from questions.models import Question

# Find question
question = Question.objects.get(id=123)

# Update fields
question.question_text = "Updated question text"
question.explanation = "Updated explanation"
question.save()
```

### 3. Bulk Import Questions

#### Prepare Data Format
Create a JSON file with questions:
```json
[
  {
    "question_text": "Question text here",
    "option_a": "Option A",
    "option_b": "Option B", 
    "option_c": "Option C",
    "option_d": "Option D",
    "correct_answer": "A",
    "year": 2023,
    "subject": 1,  # Subject ID
    "topic": 5,     # Topic ID (optional)
    "difficulty": "medium",
    "explanation": "Detailed explanation here"
  }
]
```

#### Import via API
```bash
# Use the upload endpoint
curl -X POST http://localhost:8000/api/questions/upload/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d @questions.json
```

#### Import via Management Command
```bash
# Export current data for reference
python manage.py sync_data --action=export --file=current_questions.json

# After editing, restore (this replaces all data)
python manage.py sync_data --action=restore --file=updated_questions.json
```

### 4. Finding and Fixing Issues

#### Check for Questions Without Topics
```bash
python manage.py shell
```
```python
from questions.models import Question

# Find questions without topics
questions_without_topics = Question.objects.filter(topic__isnull=True)
print(f"Found {questions_without_topics.count()} questions without topics")

# Assign topics in bulk
from questions.models import Topic
medicine_topic = Topic.objects.get(name='Cardiology', subject__name='General Medicine')

# Update questions containing "heart" or "cardiac"
heart_questions = questions_without_topics.filter(
    question_text__icontains='heart'
)
heart_questions.update(topic=medicine_topic)
```

#### Add Explanations to Questions
```python
# Find questions without explanations
no_explanation = Question.objects.filter(explanation='')
print(f"Found {no_explanation.count()} questions without explanations")

# Add explanation to specific question
question = Question.objects.get(id=123)
question.explanation = "This is the correct answer because..."
question.save()
```

### 5. Data Quality Improvements

#### Fix Question Text Formatting
```python
# Clean up question text with formatting issues
questions = Question.objects.filter(question_text__contains='\n')
for q in questions:
    q.question_text = q.question_text.replace('\n', ' ').strip()
    q.save()
```

#### Standardize Difficulty Levels
```python
# Check difficulty distribution
from django.db.models import Count
difficulty_stats = Question.objects.values('difficulty').annotate(count=Count('id'))
print(list(difficulty_stats))

# Update difficulty for specific questions
Question.objects.filter(year__lt=2020).update(difficulty='medium')
```

## 🐛 Troubleshooting Common Issues

### Issue: Questions Not Showing in Frontend

**Symptoms**: Questions exist in database but don't appear in web interface

**Solutions**:
1. **Check API Response**:
   ```bash
   curl http://localhost:8000/api/questions/?year=2020
   ```

2. **Verify is_active Status**:
   ```python
   from questions.models import Question
   inactive = Question.objects.filter(is_active=False)
   print(f"Inactive questions: {inactive.count()}")
   inactive.update(is_active=True)  # Activate if needed
   ```

3. **Check Frontend Filters**:
   - Open browser developer tools (F12)
   - Go to Network tab
   - Filter by year and check API requests
   - Look for JavaScript errors in Console tab

### Issue: CORS Errors

**Symptoms**: Frontend can't connect to backend API

**Solutions**:
1. **Check CORS Settings** in `settings.py`:
   ```python
   CORS_ALLOWED_ORIGINS = [
       "http://localhost:3000",
       "http://127.0.0.1:3000"
   ]
   ```

2. **Restart Backend Server** after changing settings

### Issue: Database Sync Problems

**Symptoms**: Production and localhost show different data

**Solutions**:
1. **Backup Production Data**:
   ```bash
   python manage.py sync_data --action=backup --file=prod_backup.json
   ```

2. **Transfer to Localhost**:
   - Copy the backup file to localhost
   - Run restore command
   ```bash
   python manage.py sync_data --action=restore --file=prod_backup.json
   ```

## 📊 Data Validation Commands

### Run Analysis Scripts
```bash
# Comprehensive data analysis
python manage.py analyze_questions

# API filtering check
python manage.py check_api_filters

# Environment comparison
python manage.py environment_comparison
```

### Regular Maintenance Tasks
```bash
# Backup before making changes
python manage.py sync_data --action=backup

# Export specific years for review
python manage.py sync_data --action=export --years="2018,2019,2020"

# Check data quality
python manage.py analyze_questions
```

## 🚀 Best Practices

1. **Always Backup** before making bulk changes
2. **Test on localhost** before applying to production
3. **Use meaningful topics** for better categorization
4. **Add explanations** to improve learning value
5. **Regular validation** to catch data issues early
6. **Document changes** for future reference
7. **Monitor API responses** for frontend issues

## 📞 Getting Help

If you encounter issues:

1. **Check the logs**: Look at Django admin logs and browser console
2. **Run analysis scripts**: Use the management commands provided
3. **Verify API endpoints**: Test with curl or Postman
4. **Check database state**: Use Django shell for direct inspection

## 🔄 Environment Sync Process

### From Production to Localhost
1. **Export Production Data**:
   ```bash
   python manage.py sync_data --action=backup --file=prod_latest.json
   ```

2. **Transfer to Local**:
   - Copy `prod_latest.json` to localhost environment

3. **Import to Local**:
   ```bash
   python manage.py sync_data --action=restore --file=prod_latest.json
   ```

### From Localhost to Production
1. **Test thoroughly** on localhost
2. **Backup Production** first
3. **Export changes** from localhost
4. **Apply to production** carefully

---

**Remember**: The issue you reported (missing 2018-2020 questions) appears to be in the frontend filtering logic, not the backend data. All years have adequate questions in the database.
