"""
تطبيق الترجمة الفورية للقرآن الكريم - نسخة محسّنة
Enhanced Quran Live Translation System
"""

# إصلاح مشكلة Unicode على Windows
import sys
import io
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import os
import time
import json
from datetime import datetime

# استيراد المكونات المحسّنة
from database import initialize_database
from cache import CacheManager
from enhanced_matcher import EnhancedMatcher
from prayer_movement_detector import PrayerMovementDetector, PrayerMovement

# ==========================================
# تهيئة Flask
# ==========================================

# المسارات
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(os.path.dirname(BASE_DIR), 'templates')
STATIC_DIR = os.path.join(os.path.dirname(BASE_DIR), 'static')

app = Flask(__name__, 
           template_folder=TEMPLATE_DIR,
           static_folder=STATIC_DIR)

app.config['SECRET_KEY'] = 'quran-live-enhanced-2025'
app.config['JSON_AS_ASCII'] = False

# تفعيل CORS
CORS(app)

# Socket.IO
socketio = SocketIO(
    app, 
    cors_allowed_origins="*",
    ping_interval=25,
    ping_timeout=60,
    async_mode='eventlet'
)

print("\n" + "="*70)
print("🌙 نظام الترجمة الفورية للقرآن الكريم - النسخة المحسّنة")
print("="*70)

# ==========================================
# تهيئة المكونات
# ==========================================

print("\n[INIT] 🔧 Initializing components...")

# قاعدة البيانات
DB_PATH = os.path.join(os.path.dirname(BASE_DIR), 'data', 'quran.db')
JSON_PATH = os.path.join(os.path.dirname(BASE_DIR), 'data', 'quran.json')

db = initialize_database(
    json_path=JSON_PATH,
    db_path=DB_PATH,
    force=False
)

# الكاش
cache = CacheManager(
    use_redis=False,  # غيّر إلى True لاستخدام Redis
    local_max_size=1000,
    ttl=3600
)

# نظام المطابقة
matcher = EnhancedMatcher(db, cache)

# كاشف حركات الصلاة
prayer_detector = PrayerMovementDetector(debug=True)

# حالة التطبيق
app_state = {
    'start_time': datetime.now(),
    'connected_clients': 0,
    'total_requests': 0
}

print("[INIT] ✅ All components initialized successfully\n")

# ==========================================
# Routes
# ==========================================

@app.route('/')
def index():
    """الصفحة الرئيسية"""
    return render_template('index.html')

@app.route('/live')
def live():
    """صفحة البث المباشر مع دعم اللغات
    
    Examples:
        /live?lang=en
        /live?lang=fr  
        /live?lang=nl
        /live?lang=ar
    """
    lang = request.args.get('lang', 'en')
    return render_template('live.html', lang=lang)

@app.route('/stats')
def stats_page():
    """صفحة الإحصائيات"""
    return render_template('stats.html')

# ==========================================
# API Endpoints
# ==========================================

@app.route('/api/health')
def health():
    """فحص صحة النظام"""
    return jsonify({
        'status': 'healthy',
        'uptime': str(datetime.now() - app_state['start_time']),
        'database': db.get_stats(),
        'cache': cache.get_stats(),
        'matcher': matcher.get_stats(),
        'prayer_detector': prayer_detector.get_prayer_stats(),
        'connected_clients': app_state['connected_clients'],
        'total_requests': app_state['total_requests']
    })

@app.route('/api/verse/<int:surah>/<int:ayah>')
def get_verse(surah, ayah):
    """
    جلب آية محددة
    
    Parameters:
        surah: رقم السورة
        ayah: رقم الآية
    
    Query params:
        lang: اللغة (ar, en, fr, nl)
    """
    start_time = time.time()
    lang = request.args.get('lang', 'ar')
    
    # محاولة الجلب من الكاش
    verse = cache.get_verse(surah, ayah)
    
    # إذا لم تكن في الكاش، جلب من قاعدة البيانات
    if not verse:
        verse = db.get_verse(surah, ayah)
        
        if verse:
            # حفظ في الكاش
            cache.set_verse(surah, ayah, verse)
    
    if not verse:
        return jsonify({'error': 'Verse not found'}), 404
    
    elapsed = (time.time() - start_time) * 1000
    
    # التحقق من آية سجدة
    is_sajdah = db.is_sajdah_verse(surah, ayah)
    
    return jsonify({
        'verse': verse,
        'is_sajdah': is_sajdah,
        'response_time_ms': round(elapsed, 2)
    })

@app.route('/api/surah/<int:surah>')
def get_surah(surah):
    """جلب سورة كاملة"""
    start_time = time.time()
    
    # محاولة الجلب من الكاش
    verses = cache.get_surah(surah)
    
    # إذا لم تكن في الكاش، جلب من قاعدة البيانات
    if not verses:
        verses = db.get_surah_verses(surah)
        
        if verses:
            # حفظ في الكاش
            cache.set_surah(surah, verses)
    
    if not verses:
        return jsonify({'error': 'Surah not found'}), 404
    
    # معلومات السورة
    surah_info = db.get_surah_info(surah)
    
    elapsed = (time.time() - start_time) * 1000
    
    return jsonify({
        'surah': surah,
        'info': surah_info,
        'verses': verses,
        'count': len(verses),
        'response_time_ms': round(elapsed, 2)
    })

@app.route('/api/sajdah')
def get_sajdah_verses():
    """جلب جميع آيات السجدة"""
    verses = db.get_all_sajdah_verses()
    
    return jsonify({
        'count': len(verses),
        'verses': verses
    })

@app.route('/api/stats')
def get_stats():
    """إحصائيات النظام"""
    return jsonify({
        'app': {
            'uptime': str(datetime.now() - app_state['start_time']),
            'connected_clients': app_state['connected_clients'],
            'total_requests': app_state['total_requests']
        },
        'database': db.get_stats(),
        'cache': cache.get_stats(),
        'matcher': matcher.get_stats(),
        'prayer': prayer_detector.get_prayer_stats()
    })

# ==========================================
# WebSocket Events
# ==========================================

@socketio.on('connect')
def handle_connect():
    """عند اتصال عميل جديد"""
    app_state['connected_clients'] += 1
    
    print(f"[WS] ✅ Client connected (total: {app_state['connected_clients']})")
    
    emit('connection_status', {
        'connected': True,
        'timestamp': datetime.now().isoformat(),
        'server_info': {
            'version': '2.0-enhanced',
            'features': [
                'database',
                'cache',
                'prayer_detection',
                'sajdah_alert',
                'sequential_prediction'
            ]
        }
    })

@socketio.on('disconnect')
def handle_disconnect():
    """عند قطع اتصال العميل"""
    app_state['connected_clients'] = max(0, app_state['connected_clients'] - 1)
    print(f"[WS] 👋 Client disconnected (remaining: {app_state['connected_clients']})")

@socketio.on('recognize_verse')
def handle_recognize(data):
    """
    التعرف على آية
    
    Data:
        text: النص المعترف عليه
        surah: رقم السورة (اختياري)
        lang: اللغة المطلوبة
        audio_energy: مستوى طاقة الصوت (اختياري)
    """
    app_state['total_requests'] += 1
    
    text = data.get('text', '').strip()
    surah = data.get('surah')
    lang = data.get('lang', 'ar')
    audio_energy = data.get('audio_energy', 0.0)
    
    if not text or len(text) < 3:
        emit('error', {'message': 'Text too short'})
        return
    
    print(f"\n[WS] 🎤 Recognizing: {text[:50]}...")
    
    # مطابقة الآية
    result = matcher.match_verse(text, surah=surah)
    
    if result['status'] == 'success':
        verse = result['matched_verse']
        
        print(f"[WS] ✅ Match found: {verse['surah']}:{verse['ayah']} "
              f"({result['confidence']:.1%}, {result['response_time_ms']:.1f}ms)")
        
        # التحقق من آية سجدة
        is_sajdah = db.is_sajdah_verse(verse['surah'], verse['ayah'])
        
        # إرسال الآية الحالية
        emit('verse_matched', {
            'verse': {
                'surah': verse['surah'],
                'ayah': verse['ayah'],
                'ar': verse['ar'],
                'translation': verse.get(lang, verse.get('en', ''))
            },
            'confidence': result['confidence'],
            'source': result['source'],
            'is_sajdah': is_sajdah,
            'response_time_ms': result['response_time_ms']
        }, broadcast=True)
        
        # إرسال الآيات التالية
        if result.get('next_verses'):
            next_data = []
            for nv in result['next_verses']:
                next_data.append({
                    'surah': nv['surah'],
                    'ayah': nv['ayah'],
                    'ar': nv['ar'],
                    'translation': nv.get(lang, nv.get('en', ''))
                })
            
            emit('next_verses', {
                'verses': next_data,
                'count': len(next_data)
            }, broadcast=True)
        
        # تنبيه سجود التلاوة
        if is_sajdah:
            sajdah_info = prayer_detector.get_sajdah_info(
                verse['surah'], 
                verse['ayah']
            )
            
            emit('sajdah_alert', {
                'verse': {
                    'surah': verse['surah'],
                    'ayah': verse['ayah'],
                    'ar': verse['ar']
                },
                'info': sajdah_info
            }, broadcast=True)
    
    else:
        print(f"[WS] ❌ No match: {result['reason']}")
        
        emit('no_match', {
            'reason': result['reason'],
            'response_time_ms': result.get('response_time_ms', 0)
        })
    
    # كشف حركات الصلاة
    movement = prayer_detector.detect_movement(text, audio_energy)
    if movement:
        prayer_detector.update_prayer_state(movement)
        
        emit('prayer_movement', {
            'movement': movement.value,
            'stats': prayer_detector.get_prayer_stats()
        }, broadcast=True)

@socketio.on('set_surah')
def handle_set_surah(data):
    """
    تعيين السورة الحالية (للتنبؤ التسلسلي)
    
    Data:
        surah: رقم السورة
    """
    surah = data.get('surah')
    
    if surah:
        matcher.set_surah(surah)
        
        # جلب معلومات السورة
        surah_info = db.get_surah_info(surah)
        
        emit('surah_set', {
            'surah': surah,
            'info': surah_info,
            'message': f'تم تعيين السورة {surah}'
        }, broadcast=True)
        
        print(f"[WS] 📖 Surah set to: {surah}")

@socketio.on('reset_matcher')
def handle_reset():
    """إعادة تعيين نظام المطابقة"""
    matcher.reset()
    prayer_detector.reset()
    
    emit('matcher_reset', {
        'message': 'تم إعادة تعيين النظام',
        'timestamp': datetime.now().isoformat()
    }, broadcast=True)
    
    print("[WS] 🔄 Matcher reset")

@socketio.on('get_stats')
def handle_get_stats():
    """جلب الإحصائيات عبر WebSocket"""
    emit('stats_update', {
        'matcher': matcher.get_stats(),
        'cache': cache.get_stats(),
        'prayer': prayer_detector.get_prayer_stats(),
        'timestamp': datetime.now().isoformat()
    })

# ==========================================
# Error Handlers
# ==========================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# ==========================================
# Cleanup
# ==========================================

def cleanup():
    """تنظيف الموارد عند الإغلاق"""
    print("\n[CLEANUP] 🧹 Cleaning up resources...")
    db.close()
    print("[CLEANUP] ✅ Cleanup complete")

import atexit
atexit.register(cleanup)

# ==========================================
# Main
# ==========================================

if __name__ == '__main__':
    print("\n" + "="*70)
    print("🚀 Starting server...")
    print("="*70)
    print(f"📍 URL: http://localhost:5000")
    print(f"📊 Stats: http://localhost:5000/api/stats")
    print(f"💚 Health: http://localhost:5000/api/health")
    print("="*70 + "\n")
    
    # تشغيل الخادم
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=False,
        use_reloader=False
    )
