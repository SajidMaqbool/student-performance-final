from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib import messages
import pandas as pd
import sqlite3
import os
import matplotlib
matplotlib.use('Agg')  # Headless mode for web rendering background plots
import matplotlib.pyplot as plt
import io
import base64

DB_NAME = "db.sqlite3"
CSV_NAME = "Student_Performance.csv"

def sync_csv_to_db():
    """Dumps all raw CSV records into the SQLite database table architecture."""
    if os.path.exists(CSV_NAME):
        conn = sqlite3.connect(DB_NAME)
        df = pd.read_csv(CSV_NAME)
        df.columns = [c.strip().lower().replace(' ', '_') for c in df.columns]
        df.to_sql("performance", conn, if_exists="replace", index=False)
        conn.commit()
        conn.close()

# Automatic database synchronization trigger on server initialization
sync_csv_to_db()

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        action = request.POST.get('action')
        
        if action == 'login':
            user = authenticate(username=username, password=password)
            if user is not None:
                auth_login(request, user)
                return redirect('dashboard')
            else:
                messages.error(request, "Invalid username or password credentials!")
        else:
            if User.objects.filter(username=username).exists():
                messages.error(request, "Username is already taken!")
            else:
                User.objects.create_user(username=username, password=password)
                messages.success(request, "Registration successful! Please log in below.")
                
    return render(request, 'login.html')

def dashboard_view(request):
    if not request.user.is_authenticated:
        return redirect('login')
        
    # Extract query filter strings from the GET request URL payload
    search_query = request.GET.get('search', '').strip().lower()
    gender_filter = request.GET.get('gender', 'All')
    school_filter = request.GET.get('school', 'All')
    
    # Secure pagination index fallback mechanisms
    try:
        page = int(request.GET.get('page', 1))
    except ValueError:
        page = 1
        
    per_page = 50
    
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM performance", conn)
    conn.close()
    
    # --- Advanced Data Filters Pipeline Segment ---
    if search_query:
        df = df[df['final_grade'].astype(str).str.lower().str.contains(search_query) | 
                df['student_id'].astype(str).str.contains(search_query)]
    if gender_filter != 'All':
        df = df[df['gender'] == gender_filter]
    if school_filter != 'All':
        df = df[df['school_type'] == school_filter]
        
    total_rows = len(df)
    total_pages = max(1, (total_rows + per_page - 1) // per_page)
    
    # Out of bounds page safety guard logic
    if page < 1:
        page = 1
    elif page > total_pages:
        page = total_pages
        
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    
    # Metric Summary Calculation Block
    metrics = {
        'total': total_rows,
        'avg': round(df['overall_score'].mean(), 1) if total_rows > 0 else 0,
        'max': df['overall_score'].max() if total_rows > 0 else 0,
        'min': df['overall_score'].min() if total_rows > 0 else 0
    }
    
    # Transform Pandas array frames into primitive native arrays for Django compilation safety
    page_data = df.iloc[start_idx:end_idx].values.tolist()
    columns = [col.replace('_', ' ').title() for col in df.columns]
    
    context = {
        'data': page_data, 
        'columns': columns, 
        'metrics': metrics,
        'page': page, 
        'total_pages': total_pages, 
        'search': search_query,
        'gender': gender_filter, 
        'school': school_filter, 
        'prev_page': page - 1, 
        'next_page': page + 1, 
        'username': request.user.username
    }
    return render(request, 'dashboard.html', context)

def charts_view(request):
    if not request.user.is_authenticated:
        return redirect('login')
        
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM performance", conn)
    conn.close()
    
    # Compile text analytics summary metrics from dataset
    if len(df) > 0:
        top_grade = df['final_grade'].value_counts().idxmax().upper()
        grade_pct = round((df['final_grade'].value_counts().max() / len(df)) * 100, 1)
        best_school = df.groupby('school_type')['overall_score'].mean().idxmax()
        avg_study = round(df['study_hours'].mean(), 1)
        insights = f"• Grade '{top_grade}' stands out as the primary group pattern, managing {grade_pct}% data density.\n• Maximum milestone variations map inside the '{best_school}' institution frameworks.\n• The collective cohort processes {avg_study} intensive weekly runtime hours."
    else:
        insights = "No active records found inside database matrix segments to parse trends."

    # Matplotlib Grid Figure Layout Setup configured for native Light Theme views
    plt.style.use('default')
    fig, axes = plt.subplots(3, 2, figsize=(11, 14))
    fig.tight_layout(pad=5.0)
    
    if len(df) > 0:
        # 1. Bar Chart Visualization
        g_c = df['final_grade'].str.upper().value_counts().sort_index()
        axes[0, 0].bar(g_c.index, g_c.values, color='#0d6efd', edgecolor='#cccccc')
        axes[0, 0].set_title("1. Bar Chart: Grade Distributions")
        axes[0, 0].grid(axis='y', linestyle='--', alpha=0.5)
        
        # 2. Pie Chart Visualization
        gen_c = df['gender'].value_counts()
        axes[0, 1].pie(gen_c.values, labels=gen_c.index, autopct='%1.1f%%', colors=['#0d6efd', '#dc3545', '#ffc107'])
        axes[0, 1].set_title("2. Pie Chart: Gender Split Balance")
        
        # 3. Line Chart Visualization
        st_trend = df.groupby('age')['study_hours'].mean().sort_index()
        axes[1, 0].plot(st_trend.index, st_trend.values, marker='o', color='#198754', linewidth=2)
        axes[1, 0].set_title("3. Line Chart: Avg Hours by Age Group")
        axes[1, 0].grid(True, linestyle='--', alpha=0.5)
        
        # 4. Histogram Visualization
        axes[1, 1].hist(df['attendance_percentage'], bins=12, color='#dc3545', edgecolor='white')
        axes[1, 1].set_title("4. Histogram: Attendance Spread Density")
        axes[1, 1].grid(axis='y', linestyle='--', alpha=0.5)
        
        # 5. Scatter Plot Visualization (Sampled to prevent client side payload lags)
        samp = df.sample(n=min(300, len(df)))
        axes[2, 0].scatter(samp['study_hours'], samp['overall_score'], color='#6f42c1', alpha=0.6, edgecolors='none')
        axes[2, 0].set_title("5. Scatter Plot: Hours vs Performance Marks")
        axes[2, 0].grid(True, linestyle='--', alpha=0.5)
    
    # Disable the 6th unused empty canvas box framework grid block
    axes[2, 1].axis('off')
    
    # Binary standard stream conversions to bypass physical storage image writes
    img = io.BytesIO()
    plt.savefig(img, format='png', bbox_inches='tight', dpi=100)
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode('utf8')
    plt.close()

    return render(request, 'charts.html', {'plot_url': plot_url, 'insights': insights, 'username': request.user.username})

def logout_view(request):
    auth_logout(request)
    return redirect('login')