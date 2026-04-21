"""
MCV | كاشف الشاشة
يقرأ شاشة الموبايل ويكشف الأشخاص فيها
يستخدم MediaProjection API
"""
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.core.window import Window
from kivy.clock import Clock
import threading

Window.clearcolor = (0.05, 0.05, 0.05, 1)

# ===== globals =====
detection_running = False
hog               = None
overlay_btn       = None
window_manager    = None
proj_thread       = None


# ===== HOG init =====
def init_hog():
    global hog
    import cv2
    hog = cv2.HOGDescriptor()
    hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())


# ===== طلب MediaProjection =====
def request_media_projection(callback):
    try:
        from jnius import autoclass, PythonJavaClass, java_method
        from android.runnable import run_on_ui_thread

        PythonActivity     = autoclass('org.kivy.android.PythonActivity')
        MediaProjectionMgr = autoclass('android.media.projection.MediaProjectionManager')
        Intent             = autoclass('android.content.Intent')

        activity = PythonActivity.mActivity
        mgr = activity.getSystemService('media_projection')
        intent = mgr.createScreenCaptureIntent()

        # نحفظ الـ callback في متغير عام
        import main as m
        m._proj_callback = callback

        activity.startActivityForResult(intent, 1001)
    except Exception as e:
        print('MediaProjection request error:', e)


# ===== لوب الكشف على الشاشة =====
def screen_detection_loop(media_projection):
    global detection_running, hog
    import cv2
    import numpy as np

    try:
        from jnius import autoclass
        ImageReader    = autoclass('android.media.ImageReader')
        PixelFormat    = autoclass('android.graphics.PixelFormat')
        DisplayMetrics = autoclass('android.util.DisplayMetrics')
        PythonActivity = autoclass('org.kivy.android.PythonActivity')

        activity = PythonActivity.mActivity
        metrics  = DisplayMetrics()
        activity.getWindowManager().getDefaultDisplay().getMetrics(metrics)

        width  = metrics.widthPixels
        height = metrics.heightPixels
        dpi    = metrics.densityDpi

        # ImageReader لاستقبال الإطارات
        reader = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, 2)
        surface = reader.getSurface()

        vd = media_projection.createVirtualDisplay(
            'MCVDetector', width, height, dpi,
            1,  # VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR
            surface, None, None
        )

        while detection_running:
            image = reader.acquireLatestImage()
            if image is None:
                continue

            planes = image.getPlanes()
            buf = planes[0].getBuffer()

            # تحويل لـ numpy
            import array
            byte_arr = bytearray(buf.remaining())
            buf.get(byte_arr)
            frame = np.frombuffer(byte_arr, dtype=np.uint8).reshape((height, width, 4))
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)
            image.close()

            # تصغير للسرعة
            scale = 0.35
            small = cv2.resize(frame_bgr, (int(width*scale), int(height*scale)))

            boxes, _ = hog.detectMultiScale(
                small,
                winStride=(8, 8),
                padding=(4, 4),
                scale=1.05
            )

            # تحديث الزر
            count = len(boxes)
            update_overlay_count(count)

        reader.close()
        vd.release()
        media_projection.stop()

    except Exception as e:
        print('Screen detection error:', e)


# ===== تحديث لون ونص الزر العائم =====
def update_overlay_count(count):
    try:
        from jnius import autoclass
        from android.runnable import run_on_ui_thread
        Color = autoclass('android.graphics.Color')

        @run_on_ui_thread
        def _update():
            if overlay_btn is None:
                return
            if count == 0:
                overlay_btn.setBackgroundColor(Color.parseColor('#00C853'))
                overlay_btn.setText('\u25B6')
            else:
                overlay_btn.setBackgroundColor(Color.parseColor('#D50000'))
                overlay_btn.setText(str(count))
        _update()
    except Exception as e:
        print('update error:', e)


# ===== بدء / إيقاف الكشف =====
def start_detection(media_projection):
    global detection_running, proj_thread
    detection_running = True
    proj_thread = threading.Thread(
        target=screen_detection_loop,
        args=(media_projection,),
        daemon=True
    )
    proj_thread.start()


def stop_detection():
    global detection_running
    detection_running = False
    update_overlay_count(0)


# ===== إنشاء الزر العائم =====
def create_floating_button():
    global overlay_btn, window_manager

    try:
        from jnius import autoclass, PythonJavaClass, java_method
        from android.runnable import run_on_ui_thread

        LayoutParams   = autoclass('android.view.WindowManager$LayoutParams')
        AndroidButton  = autoclass('android.widget.Button')
        Color          = autoclass('android.graphics.Color')
        Gravity        = autoclass('android.view.Gravity')
        Build          = autoclass('android.os.Build')
        PythonActivity = autoclass('org.kivy.android.PythonActivity')

        activity = PythonActivity.mActivity
        window_manager = activity.getSystemService('window')

        params = LayoutParams()
        params.type = (LayoutParams.TYPE_APPLICATION_OVERLAY
                       if Build.VERSION.SDK_INT >= 26
                       else LayoutParams.TYPE_PHONE)
        params.flags = (LayoutParams.FLAG_NOT_FOCUSABLE |
                        LayoutParams.FLAG_LAYOUT_IN_SCREEN)
        params.width   = 160
        params.height  = 160
        params.gravity = Gravity.TOP | Gravity.END
        params.x = 20
        params.y = 200

        class BtnClick(PythonJavaClass):
            __javainterfaces__ = ['android/view/View$OnClickListener']
            @java_method('(Landroid/view/View;)V')
            def onClick(self, view):
                if detection_running:
                    stop_detection()
                else:
                    request_media_projection(start_detection)

        @run_on_ui_thread
        def _add():
            global overlay_btn
            overlay_btn = AndroidButton(activity)
            overlay_btn.setText('\u25B6')
            overlay_btn.setTextSize(24.0)
            overlay_btn.setTextColor(Color.WHITE)
            overlay_btn.setBackgroundColor(Color.parseColor('#00C853'))
            overlay_btn.setOnClickListener(BtnClick())
            window_manager.addView(overlay_btn, params)
        _add()

    except Exception as e:
        print('Floating button error:', e)


def remove_floating_button():
    try:
        from android.runnable import run_on_ui_thread
        @run_on_ui_thread
        def _r():
            if overlay_btn and window_manager:
                window_manager.removeView(overlay_btn)
        _r()
    except Exception:
        pass


# ============================================================
# KIVY UI
# ============================================================
class MainUI(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', padding=[36, 52, 36, 36], spacing=20, **kwargs)

        self.add_widget(Label(
            text='[b]MCV | كاشف الشاشة[/b]',
            markup=True, font_size='22sp',
            color=(1, 0.12, 0.12, 1), size_hint=(1, 0.15)
        ))

        self.add_widget(Label(
            text='يقرأ شاشة موبايلك ويكشف الأشخاص\nفي أي لعبة أو فيديو أو تطبيق\nاضغط تشغيل لتفعيل الزر العائم',
            font_size='13sp', color=(0.6, 0.6, 0.6, 1),
            halign='center', size_hint=(1, 0.25)
        ))

        self.launch_btn = Button(
            text='تشغيل',
            font_size='18sp', size_hint=(0.7, 0.13),
            pos_hint={'center_x': 0.5},
            background_normal='', background_color=(0.85, 0.07, 0.07, 1)
        )
        self.launch_btn.bind(on_press=self.launch)
        self.add_widget(self.launch_btn)

        self.status = Label(
            text='', font_size='12sp',
            color=(0.45, 0.45, 0.45, 1),
            halign='center', size_hint=(1, 0.3)
        )
        self.add_widget(self.status)

    def launch(self, *a):
        init_hog()
        create_floating_button()
        self.launch_btn.text = '✅ الزر العائم شغال'
        self.launch_btn.background_color = (0.2, 0.2, 0.2, 1)
        self.launch_btn.disabled = True
        self.status.text = (
            'الزر الأخضر ▶ = اضغطه لبدء قراءة الشاشة\n'
            'الرقم الأحمر = عدد الأشخاص المكتشفين\n'
            'يمكنك إغلاق التطبيق والزر يبقى فوق كل شيء'
        )


# ============================================================
# APP
# ============================================================
class ScreenDetectorApp(App):
    def build(self):
        self.title = 'MCV كاشف الشاشة'
        self._ask_permissions()
        return MainUI()

    def _ask_permissions(self):
        try:
            from android.permissions import request_permissions, Permission
            request_permissions([Permission.FOREGROUND_SERVICE])

            from jnius import autoclass
            Settings       = autoclass('android.provider.Settings')
            Intent         = autoclass('android.content.Intent')
            Uri            = autoclass('android.net.Uri')
            PythonActivity = autoclass('org.kivy.android.PythonActivity')

            activity = PythonActivity.mActivity

            # إذن الظهور فوق التطبيقات
            if not Settings.canDrawOverlays(activity):
                intent = Intent(
                    Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    Uri.parse('package:' + activity.getPackageName())
                )
                activity.startActivity(intent)
        except Exception:
            pass

    def on_stop(self):
        stop_detection()
        remove_floating_button()


if __name__ == '__main__':
    ScreenDetectorApp().run()
