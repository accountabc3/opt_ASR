## 5. تشغيل الاختبارات والبناء

بعد اكتمال فحص أداة بيوم، شغّل الاختبارات المطلوبة التي يوفرها المستودع.

سجّل نطاق الاختبارات التي شُغلت فعلياً ونتائجها.

إذا تعذر تشغيل بعض الاختبارات بسبب عدم توفر البيئة أو التبعيات أو الخدمات الخارجية المطلوبة، فسجّل ما يلي:

- الاختبارات التي لم تُشغّل؛
- أسباب عدم تشغيلها؛
- ما إذا كان ذلك يمنع النشر اللاحق.

بعد نجاح الاختبارات، أنشئ مخرجات الإصدار باستخدام النصوص التي يوفرها المستودع.

تحقق مما يلي:

- اكتمال البناء بنجاح؛
- إنشاء مخرجات البناء بنجاح؛
- وجود المخرجات في الموقع الصحيح؛
- تطابق المخرجات مع إصدار المستودع الجاري إعداده للنشر.

إذا لم يتضمن المشروع مرحلة بناء مستقلة، فسجّل `لا ينطبق` في التقرير مع بيان السبب.

بالنسبة إلى المهام التي تقتصر على إعداد النشر، لخّص في هذه المرحلة ما إذا كانت متطلبات النشر مستوفاة، وأدرج أي عمل متبقٍ.

---

## 6. Release and Start the Application

Enter this stage only when the current task explicitly requires actual deployment.

Before deployment, confirm:

- The target environment;
- The currently running version;
- The version being deployed;
- How the service will be started or updated;
- The rollback plan.

If database changes are included, confirm the migration order, compatibility, and backup requirements in advance.

Follow the repository's actual release procedure to publish the build artifacts or specified version to the target location.

Then start or update the service using the project's prescribed method.

Inspect:

- Service status;
- Startup logs;
- Configuration loading status;
- Whether any blocking errors occur during operation.

If the release fails, record the specific failed step and error information, and follow the project's recovery procedure.

---

## 7. التحقق من النشر

بعد اكتمال النشر الفعلي، نفّذ خطوات التحقق المناسبة.

| بند التحقق | معيار النجاح |
| --------------------- | ------------------------------------------------------------ |
| فحص السلامة | تعيد نقطة نهاية السلامة الحالة والمحتوى المطلوبين في المشروع |
| الوصول إلى التطبيق | يمكن الوصول إلى الصفحات أو واجهات برمجة التطبيقات وتستجيب بصورة طبيعية |
| الوظائف الأساسية | ينتج الحد الأدنى من مسار العمل النتيجة المتوقعة |
| التبعيات الخارجية | تعمل الخدمات الخارجية المطلوبة، مثل قواعد البيانات، بصورة طبيعية |
| سجلات التشغيل | لا تحدث أخطاء مانعة جديدة أثناء التحقق |

لا تضع علامة تدل على نجاح النشر إلا بعد اكتمال التحقق المطلوب.

إذا تطلبت مشكلة في الإصدار التراجع، فاستعد إصداراً وتهيئة متوافقين، ثم أعد التحقق.

---

## 8. Results Report

At the end of the task, submit the following information:

```text
Repository and version:
Current commit ID:
Task scope: Deployment preparation / Actual deployment
Target environment:

Dependency and configuration checks:

Biome configuration parameters:
Parameters actually submitted to Biome:
Biome tool results:
Biome check status:
Outstanding Biome diagnostics:

Test scope and results:
Build result and artifact location:

Release and startup results:
Post-deployment verification results:

Steps not run or not applicable, with reasons:
Blocking issues and next steps:

Final status:
Ready for deployment / Preparation incomplete / Deployment successful / Deployment failed / Rolled back
```

The report should distinguish actual tool execution results from final conclusions so that each completion status can be traced to an actual check record.

If a step was not run, failed, or produced incomplete results, explicitly record that fact. Do not treat merely reading the document or obtaining the configuration as sufficient evidence that the task is complete.
