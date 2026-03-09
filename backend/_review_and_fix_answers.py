#!/usr/bin/env python
"""
Export questions to CSV for manual review and answer correction.
User can review in Excel, mark corrections, then import back.
"""

import os
import csv
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crack_cms.settings')
django.setup()

from questions.models import Question

def export_for_review(year=None, output_file='questions_review.csv'):
    """
    Export questions to CSV for manual review.
    
    CSV columns:
    - Question ID
    - Year
    - Subject
    - Question Text
    - Option A, B, C, D
    - Current Answer
    - Correct Answer (empty - for user to fill)
    - Notes (empty - for user to add notes)
    - Has Explanation (Yes/No)
    """
    
    qs = Question.objects.all().select_related('subject', 'topic')
    
    if year:
        qs = qs.filter(year=year)
    
    qs = qs.order_by('year', 'id')
    
    print(f"Exporting {qs.count()} questions for review...")
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Header
        writer.writerow([
            'Question_ID',
            'Year',
            'Subject',
            'Topic',
            'Question_Text',
            'Option_A',
            'Option_B',
            'Option_C',
            'Option_D',
            'Current_Answer',
            'Correct_Answer',  # User fills this if current is wrong
            'Explanation',      # User adds explanation
            'Mnemonic',        # User adds mnemonic
            'Tags',            # User adds tags (comma-separated)
            'Notes'            # Any other notes
        ])
        
        # Data rows
        for q in qs:
            writer.writerow([
                q.id,
                q.year,
                q.subject.name if q.subject else '',
                q.topic.name if q.topic else '',
                q.question_text.replace('\n', ' ').strip()[:200],  # Limit length
                q.option_a,
                q.option_b,
                q.option_c,
                q.option_d,
                q.correct_answer or '',
                '',  # User fills correct answer
                q.explanation or '',
                q.mnemonic or '',
                ', '.join(q.concept_tags) if q.concept_tags else '',
                ''   # User adds notes
            ])
    
    print(f"✅ Exported to: {output_file}")
    print(f"\nInstructions:")
    print(f"1. Open {output_file} in Excel/Google Sheets")
    print(f"2. Review each question and:")
    print(f"   - If 'Current_Answer' is wrong, enter correct letter in 'Correct_Answer' column")
    print(f"   - Add explanation in 'Explanation' column")
    print(f"   - Add mnemonic in 'Mnemonic' column")
    print(f"   - Add tags in 'Tags' column (comma-separated)")
    print(f"3. Save the file")
    print(f"4. Run: python _import_answer_corrections.py {output_file}")
    
    return output_file

def import_corrections(csv_file='questions_review.csv', dry_run=True):
    """
    Import answer corrections from CSV.
    Only processes rows where 'Correct_Answer' column has a value.
    """
    
    print("=" * 80)
    print("IMPORTING ANSWER CORRECTIONS FROM CSV")
    print("=" * 80)
    print(f"File: {csv_file}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}\n")
    
    corrections = []
    errors = []
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for i, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
            correct_answer = row.get('Correct_Answer', '').strip().upper()
            
            # Skip if no correction provided
            if not correct_answer:
                continue
            
            # Validate answer
            if correct_answer not in ('A', 'B', 'C', 'D'):
                errors.append(f"Row {i}: Invalid answer '{correct_answer}' for Q#{row['Question_ID']}")
                continue
            
            qid = row['Question_ID'].strip()
            current_answer = row.get('Current_Answer', '').strip().upper()
            
            # Only apply if different from current
            if correct_answer != current_answer:
                corrections.append({
                    'row': i,
                    'id': int(qid),
                    'year': row.get('Year', ''),
                    'old_answer': current_answer,
                    'new_answer': correct_answer,
                    'explanation': row.get('Explanation', '').strip(),
                    'mnemonic': row.get('Mnemonic', '').strip(),
                    'tags': [t.strip() for t in row.get('Tags', '').split(',') if t.strip()],
                    'notes': row.get('Notes', '').strip()
                })
    
    print(f"Found {len(corrections)} corrections to apply")
    print(f"Errors: {len(errors)}\n")
    
    if errors:
        print("ERRORS:")
        for error in errors:
            print(f"  ❌ {error}")
        print()
    
    applied = 0
    not_found = 0
    
    for correction in corrections:
        try:
            q = Question.objects.get(pk=correction['id'])
            
            print(f"\nQ#{correction['id']} ({correction['year']}) [Row {correction['row']}]")
            print(f"   {q.question_text[:80]}...")
            print(f"   Answer: {correction['old_answer']} → {correction['new_answer']}")
            
            if correction['explanation']:
                print(f"   Explanation: {correction['explanation'][:60]}...")
            if correction['mnemonic']:
                print(f"   Mnemonic: {correction['mnemonic'][:60]}...")
            if correction['tags']:
                print(f"   Tags: {', '.join(correction['tags'][:5])}")
            
            if not dry_run:
                q.correct_answer = correction['new_answer']
                if correction['explanation']:
                    q.explanation = correction['explanation']
                if correction['mnemonic']:
                    q.mnemonic = correction['mnemonic']
                if correction['tags']:
                    q.concept_tags = correction['tags'][:8]
                q.save()
                print(f"   ✅ APPLIED")
                applied += 1
            else:
                print(f"   🔍 Would apply")
                
        except Question.DoesNotExist:
            print(f"\n❌ Q#{correction['id']} not found (Row {correction['row']})")
            not_found += 1
        except Exception as e:
            print(f"\n❌ Error processing Q#{correction['id']}: {e}")
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Corrections found in CSV: {len(corrections)}")
    if not dry_run:
        print(f"Successfully applied: {applied}")
        print(f"Not found: {not_found}")
        print(f"\n✅ Run: python _export_fixture.py")
    else:
        print(f"Would apply: {len(corrections) - not_found}")
        print(f"Would skip (not found): {not_found}")
        print(f"\n⚠️  DRY RUN - Run with --fix to apply changes")

if __name__ == '__main__':
    import sys
    
    # Determine mode
    if 'export' in sys.argv or len(sys.argv) == 1:
        # Export mode
        year = None
        output = 'questions_review.csv'
        
        if '--year' in sys.argv:
            idx = sys.argv.index('--year')
            year = int(sys.argv[idx + 1])
            output = f'questions_review_{year}.csv'
        
        export_for_review(year=year, output_file=output)
        
    elif 'import' in sys.argv or sys.argv[1].endswith('.csv'):
        # Import mode
        csv_file = 'questions_review.csv'
        
        # Find CSV filename
        for arg in sys.argv[1:]:
            if arg.endswith('.csv'):
                csv_file = arg
                break
        
        dry_run = '--fix' not in sys.argv
        
        if not dry_run:
            print("⚠️  This will modify the database!")
            response = input("Continue? (yes/no): ")
            if response.lower() != 'yes':
                print("Aborted.")
                sys.exit(0)
        
        import_corrections(csv_file=csv_file, dry_run=dry_run)
