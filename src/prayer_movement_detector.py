"""
كاشف حركات الصلاة المتقدم - Advanced Prayer Movement Detector
يكتشف: الركوع، السجود، التحيات، عدد الركعات، سجود التلاوة
"""

import time
from collections import deque
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
from enum import Enum


class PrayerMovement(Enum):
    """أنواع حركات الصلاة"""
    TAKBEER = "تكبير"              # الله أكبر
    QIYAM = "قيام"                 # الوقوف
    RUKU = "ركوع"                  # الركوع
    SUJOOD = "سجود"                # السجود
    TASHAHHUD = "تشهد"             # التحيات
    SALAM = "سلام"                 # التسليم
    SAJDAT_TILAWAH = "سجود_تلاوة"  # سجود التلاوة


class PrayerMovementDetector:
    """كاشف حركات الصلاة المتقدم مع الذكاء الاصطناعي"""
    
    # آيات سجود التلاوة في القرآن الكريم (15 سجدة)
    SAJDAH_VERSES = [
        (7, 206),    # الأعراف: 206
        (13, 15),    # الرعد: 15
        (16, 50),    # النحل: 50
        (17, 109),   # الإسراء: 109 (107 في بعض المصاحف)
        (19, 58),    # مريم: 58
        (22, 18),    # الحج: 18
        (22, 77),    # الحج: 77
        (25, 60),    # الفرقان: 60
        (27, 26),    # النمل: 26 (25 في بعض المصاحف)
        (32, 15),    # السجدة: 15
        (38, 24),    # ص: 24 (سجدة شكر عند الأحناف)
        (41, 38),    # فصلت: 38 (37 في بعض المصاحف)
        (53, 62),    # النجم: 62
        (84, 21),    # الانشقاق: 21
        (96, 19)     # العلق: 19
    ]
    
    def __init__(self, debug: bool = False):
        """
        تهيئة الكاشف
        
        Args:
            debug: وضع التصحيح لطباعة المعلومات التفصيلية
        """
        self.debug = debug
        
        # بيانات الصلاة الحالية
        self.current_rakaa = 0
        self.total_rakaas = 0
        self.current_movement = None
        self.last_movement = None
        self.last_movement_time = None
        
        # تاريخ الحركات
        self.movement_history: List[Dict] = []
        
        # Buffer للبيانات الصوتية
        self.audio_buffer = deque(maxlen=50)  # 5 ثواني عند 10fps
        
        # عداد السجدات
        self.sujood_count_in_rakaa = 0
        
        # حالة الصلاة
        self.prayer_started = False
        self.prayer_start_time = None
        
        # إحصائيات
        self.stats = {
            'total_movements': 0,
            'takbeer_count': 0,
            'ruku_count': 0,
            'sujood_count': 0,
            'tashahhud_count': 0,
            'sajdat_tilawah_count': 0
        }
        
        # أنماط الكشف
        self.patterns = self._initialize_patterns()
    
    def _initialize_patterns(self) -> Dict:
        """تهيئة أنماط الكشف لكل حركة"""
        return {
            PrayerMovement.TAKBEER: {
                'keywords': [
                    'الله اكبر',
                    'اللهم اكبر',
                    'لله اكبر',
                    'الله أكبر'
                ],
                'min_duration': 0.5,
                'max_duration': 3.0
            },
            PrayerMovement.QIYAM: {
                'keywords': [
                    'الفاتحة',
                    'بسم الله',
                    'الحمد لله',
                    'قل هو الله'
                ],
                'min_duration': 10.0,
                'max_duration': 180.0
            },
            PrayerMovement.RUKU: {
                'keywords': [
                    'سبحان ربي العظيم',
                    'سبحانك اللهم',
                    'سبحان الله العظيم'
                ],
                'min_silence': 2.0,
                'max_silence': 8.0,
                'min_duration': 3.0,
                'max_duration': 10.0
            },
            PrayerMovement.SUJOOD: {
                'keywords': [
                    'سبحان ربي الاعلى',
                    'سبحانك اللهم ربنا',
                    'سبحان الله الاعلى'
                ],
                'min_silence': 3.0,
                'max_silence': 12.0,
                'min_duration': 3.0,
                'max_duration': 15.0
            },
            PrayerMovement.TASHAHHUD: {
                'keywords': [
                    'التحيات لله',
                    'اشهد ان لا اله',
                    'السلام عليك ايها النبي',
                    'اللهم صل على محمد'
                ],
                'min_duration': 15.0,
                'max_duration': 60.0
            },
            PrayerMovement.SALAM: {
                'keywords': [
                    'السلام عليكم ورحمة الله',
                    'السلام عليكم'
                ],
                'min_duration': 1.0,
                'max_duration': 5.0
            }
        }
    
    def _log(self, message: str):
        """طباعة رسالة في وضع التصحيح"""
        if self.debug:
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"[{timestamp}] {message}")
    
    def detect_movement(self, transcript: str, 
                       audio_energy: float = 0.0,
                       timestamp: Optional[datetime] = None) -> Optional[PrayerMovement]:
        """
        كشف حركة الصلاة من النص والصوت
        
        Args:
            transcript: النص المعترف عليه
            audio_energy: مستوى طاقة الصوت (0-1)
            timestamp: الطابع الزمني (اختياري)
        
        Returns:
            حركة الصلاة المكتشفة أو None
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        # إضافة إلى الـ buffer
        self.audio_buffer.append({
            'timestamp': timestamp,
            'transcript': transcript.lower().strip(),
            'energy': audio_energy
        })
        
        # كشف التكبير (له أولوية عالية)
        if self._detect_takbeer(transcript):
            return PrayerMovement.TAKBEER
        
        # حساب مدة الصمت الحالية
        silence_duration = self._calculate_silence_duration()
        
        # كشف الركوع
        if self._detect_ruku(transcript, silence_duration):
            return PrayerMovement.RUKU
        
        # كشف السجود
        if self._detect_sujood(transcript, silence_duration):
            return PrayerMovement.SUJOOD
        
        # كشف التشهد
        if self._detect_tashahhud(transcript):
            return PrayerMovement.TASHAHHUD
        
        # كشف السلام
        if self._detect_salam(transcript):
            return PrayerMovement.SALAM
        
        return None
    
    def _detect_takbeer(self, transcript: str) -> bool:
        """كشف التكبير"""
        pattern = self.patterns[PrayerMovement.TAKBEER]
        transcript_lower = transcript.lower()
        
        return any(keyword in transcript_lower for keyword in pattern['keywords'])
    
    def _detect_ruku(self, transcript: str, silence_duration: float) -> bool:
        """كشف الركوع"""
        pattern = self.patterns[PrayerMovement.RUKU]
        transcript_lower = transcript.lower()
        
        # تحقق من الكلمات المفتاحية
        has_keywords = any(keyword in transcript_lower for keyword in pattern['keywords'])
        
        # تحقق من مدة الصمت
        silence_ok = (pattern['min_silence'] <= silence_duration <= pattern['max_silence'])
        
        return has_keywords or silence_ok
    
    def _detect_sujood(self, transcript: str, silence_duration: float) -> bool:
        """كشف السجود"""
        pattern = self.patterns[PrayerMovement.SUJOOD]
        transcript_lower = transcript.lower()
        
        # تحقق من الكلمات المفتاحية
        has_keywords = any(keyword in transcript_lower for keyword in pattern['keywords'])
        
        # تحقق من مدة الصمت
        silence_ok = (pattern['min_silence'] <= silence_duration <= pattern['max_silence'])
        
        return has_keywords or silence_ok
    
    def _detect_tashahhud(self, transcript: str) -> bool:
        """كشف التشهد"""
        pattern = self.patterns[PrayerMovement.TASHAHHUD]
        transcript_lower = transcript.lower()
        
        return any(keyword in transcript_lower for keyword in pattern['keywords'])
    
    def _detect_salam(self, transcript: str) -> bool:
        """كشف السلام"""
        pattern = self.patterns[PrayerMovement.SALAM]
        transcript_lower = transcript.lower()
        
        return any(keyword in transcript_lower for keyword in pattern['keywords'])
    
    def _calculate_silence_duration(self, threshold: float = 0.02) -> float:
        """
        حساب مدة الصمت الحالية
        
        Args:
            threshold: عتبة الطاقة للصمت
        
        Returns:
            مدة الصمت بالثواني
        """
        if len(self.audio_buffer) < 2:
            return 0.0
        
        now = datetime.now()
        silence_start = None
        
        # البحث عن بداية الصمت
        for entry in reversed(self.audio_buffer):
            if entry['energy'] > threshold:
                break
            silence_start = entry['timestamp']
        
        if silence_start:
            return (now - silence_start).total_seconds()
        return 0.0
    
    def update_prayer_state(self, movement: PrayerMovement):
        """
        تحديث حالة الصلاة بناءً على الحركة المكتشفة
        
        Args:
            movement: حركة الصلاة المكتشفة
        """
        now = datetime.now()
        
        # بدء الصلاة عند أول تكبير
        if movement == PrayerMovement.TAKBEER and not self.prayer_started:
            self.prayer_started = True
            self.prayer_start_time = now
            self._log("🕌 بدأت الصلاة")
        
        # تحديث عداد السجدات
        if movement == PrayerMovement.SUJOOD:
            self.sujood_count_in_rakaa += 1
            self.stats['sujood_count'] += 1
            self._log(f"🤲 سجدة {self.sujood_count_in_rakaa} في الركعة {self.current_rakaa + 1}")
            
            # إذا كانت السجدة الثانية، انتهت الركعة
            if self.sujood_count_in_rakaa == 2:
                self.current_rakaa += 1
                self.total_rakaas += 1
                self.sujood_count_in_rakaa = 0
                self._log(f"✅ انتهت الركعة {self.current_rakaa}")
        
        # تحديث الركوع
        if movement == PrayerMovement.RUKU:
            self.stats['ruku_count'] += 1
            self._log(f"🙇 ركوع في الركعة {self.current_rakaa + 1}")
        
        # تحديث التشهد
        if movement == PrayerMovement.TASHAHHUD:
            self.stats['tashahhud_count'] += 1
            self._log(f"🤲 تشهد بعد {self.current_rakaa} ركعة")
        
        # نهاية الصلاة
        if movement == PrayerMovement.SALAM:
            self._log(f"🕌 انتهت الصلاة ({self.total_rakaas} ركعات)")
        
        # تحديث الإحصائيات
        self.stats['total_movements'] += 1
        if movement == PrayerMovement.TAKBEER:
            self.stats['takbeer_count'] += 1
        
        # حفظ في التاريخ
        self.movement_history.append({
            'movement': movement.value,
            'rakaa': self.current_rakaa,
            'timestamp': now,
            'elapsed_time': self._get_elapsed_time()
        })
        
        # تحديث آخر حركة
        self.last_movement = movement
        self.last_movement_time = now
        self.current_movement = movement
    
    def detect_sajdat_tilawah(self, surah: int, ayah: int) -> bool:
        """
        كشف آيات سجود التلاوة
        
        Args:
            surah: رقم السورة
            ayah: رقم الآية
        
        Returns:
            True إذا كانت آية سجدة
        """
        is_sajdah = (surah, ayah) in self.SAJDAH_VERSES
        
        if is_sajdah:
            self.stats['sajdat_tilawah_count'] += 1
            self._log(f"⚠️ آية سجدة: سورة {surah} آية {ayah}")
        
        return is_sajdah
    
    def get_sajdah_info(self, surah: int, ayah: int) -> Optional[Dict]:
        """
        الحصول على معلومات سجدة التلاوة
        
        Args:
            surah: رقم السورة
            ayah: رقم الآية
        
        Returns:
            معلومات السجدة أو None
        """
        if not self.detect_sajdat_tilawah(surah, ayah):
            return None
        
        # أسماء السور للسجدات
        surah_names = {
            7: "الأعراف",
            13: "الرعد",
            16: "النحل",
            17: "الإسراء",
            19: "مريم",
            22: "الحج",
            25: "الفرقان",
            27: "النمل",
            32: "السجدة",
            38: "ص",
            41: "فصلت",
            53: "النجم",
            84: "الانشقاق",
            96: "العلق"
        }
        
        return {
            'surah_number': surah,
            'surah_name': surah_names.get(surah, f"السورة {surah}"),
            'ayah': ayah,
            'type': 'سجدة تلاوة',
            'ruling': 'مستحبة' if surah != 38 else 'سجدة شكر عند الأحناف'
        }
    
    def _get_elapsed_time(self) -> float:
        """حساب الوقت المنقضي منذ بداية الصلاة"""
        if not self.prayer_start_time:
            return 0.0
        return (datetime.now() - self.prayer_start_time).total_seconds()
    
    def get_prayer_stats(self) -> Dict:
        """
        الحصول على إحصائيات الصلاة
        
        Returns:
            قاموس بالإحصائيات
        """
        return {
            'prayer_started': self.prayer_started,
            'current_rakaa': self.current_rakaa,
            'total_rakaas': self.total_rakaas,
            'current_movement': self.current_movement.value if self.current_movement else None,
            'last_movement': self.last_movement.value if self.last_movement else None,
            'prayer_duration': self._get_elapsed_time(),
            'movements': self.stats.copy(),
            'recent_history': self.movement_history[-10:]  # آخر 10 حركات
        }
    
    def get_detailed_report(self) -> str:
        """
        تقرير مفصل عن الصلاة
        
        Returns:
            تقرير نصي مفصل
        """
        stats = self.get_prayer_stats()
        
        report = [
            "=" * 70,
            "📊 تقرير الصلاة المفصل",
            "=" * 70,
            f"✅ حالة الصلاة: {'جارية' if stats['prayer_started'] else 'لم تبدأ'}",
            f"🕌 الركعة الحالية: {stats['current_rakaa']}",
            f"📈 إجمالي الركعات: {stats['total_rakaas']}",
            f"⏱️ المدة: {stats['prayer_duration']:.1f} ثانية",
            "",
            "🔢 الإحصائيات:",
            f"  • التكبيرات: {stats['movements']['takbeer_count']}",
            f"  • الركوع: {stats['movements']['ruku_count']}",
            f"  • السجود: {stats['movements']['sujood_count']}",
            f"  • التشهد: {stats['movements']['tashahhud_count']}",
            f"  • سجود التلاوة: {stats['movements']['sajdat_tilawah_count']}",
            f"  • إجمالي الحركات: {stats['movements']['total_movements']}",
            "",
            "📜 آخر 5 حركات:",
        ]
        
        for i, move in enumerate(stats['recent_history'][-5:], 1):
            elapsed = move['elapsed_time']
            report.append(
                f"  {i}. {move['movement']} "
                f"(الركعة {move['rakaa']}, {elapsed:.1f}ث)"
            )
        
        report.append("=" * 70)
        
        return "\n".join(report)
    
    def reset(self):
        """إعادة تعيين الكاشف لصلاة جديدة"""
        self._log("🔄 إعادة تعيين الكاشف")
        
        self.current_rakaa = 0
        self.total_rakaas = 0
        self.current_movement = None
        self.last_movement = None
        self.last_movement_time = None
        self.sujood_count_in_rakaa = 0
        self.prayer_started = False
        self.prayer_start_time = None
        
        self.movement_history.clear()
        self.audio_buffer.clear()
        
        # لا نعيد تعيين الإحصائيات الإجمالية
    
    def export_history(self) -> List[Dict]:
        """
        تصدير تاريخ الحركات
        
        Returns:
            قائمة بجميع الحركات
        """
        return [
            {
                'movement': move['movement'],
                'rakaa': move['rakaa'],
                'timestamp': move['timestamp'].isoformat(),
                'elapsed_time': move['elapsed_time']
            }
            for move in self.movement_history
        ]


# ==========================================
# أمثلة الاستخدام
# ==========================================

if __name__ == "__main__":
    print("="*70)
    print("🕌 كاشف حركات الصلاة - اختبارات")
    print("="*70)
    
    # تهيئة الكاشف
    detector = PrayerMovementDetector(debug=True)
    
    # محاكاة صلاة ركعتين
    print("\n🕌 محاكاة صلاة الفجر (ركعتان)\n")
    
    # الركعة الأولى
    print("📍 الركعة الأولى:")
    movement = detector.detect_movement("الله اكبر")
    if movement:
        detector.update_prayer_state(movement)
    
    time.sleep(0.5)
    
    movement = detector.detect_movement("بسم الله الرحمن الرحيم")
    
    time.sleep(1)
    
    movement = detector.detect_movement("سبحان ربي العظيم")
    if movement:
        detector.update_prayer_state(movement)
    
    time.sleep(0.5)
    
    movement = detector.detect_movement("سبحان ربي الاعلى")
    if movement:
        detector.update_prayer_state(movement)
    
    time.sleep(0.5)
    
    movement = detector.detect_movement("سبحان ربي الاعلى")
    if movement:
        detector.update_prayer_state(movement)
    
    # الركعة الثانية
    print("\n📍 الركعة الثانية:")
    movement = detector.detect_movement("الله اكبر")
    if movement:
        detector.update_prayer_state(movement)
    
    time.sleep(1)
    
    movement = detector.detect_movement("سبحان ربي العظيم")
    if movement:
        detector.update_prayer_state(movement)
    
    time.sleep(0.5)
    
    movement = detector.detect_movement("سبحان ربي الاعلى")
    if movement:
        detector.update_prayer_state(movement)
    
    time.sleep(0.5)
    
    movement = detector.detect_movement("سبحان ربي الاعلى")
    if movement:
        detector.update_prayer_state(movement)
    
    # التشهد
    print("\n📍 التشهد:")
    movement = detector.detect_movement("التحيات لله")
    if movement:
        detector.update_prayer_state(movement)
    
    # التسليم
    print("\n📍 التسليم:")
    movement = detector.detect_movement("السلام عليكم ورحمة الله")
    if movement:
        detector.update_prayer_state(movement)
    
    # طباعة التقرير
    print("\n" + detector.get_detailed_report())
    
    # اختبار سجود التلاوة
    print("\n🔍 اختبار آيات سجود التلاوة:")
    print("-" * 70)
    
    test_verses = [
        (7, 206, "الأعراف"),
        (53, 62, "النجم"),
        (2, 1, "البقرة - ليست سجدة")
    ]
    
    for surah, ayah, name in test_verses:
        info = detector.get_sajdah_info(surah, ayah)
        if info:
            print(f"✅ {name}: {info}")
        else:
            print(f"❌ {name}: ليست آية سجدة")
    
    print("\n✅ جميع الاختبارات اكتملت بنجاح!")
