288
289# In real implementation, this would be triggered by UI events
290if not session_active:  # This would be set by UI signal
291    await handle_session_end(db, user_id, latest_accuracy, cfg)
292    break
293
294async def main():
295    cfg = yaml.safe_load(open("config.yaml"))
296    db = CoachDB(cfg["database"]["path"]); await db.init()
297
298    # Create or get user (for demo, single user 'default')
299    user_id = await db.create_user("default")
300    session_id = await db.create_session(user_id)
301
302    if GUI_AVAILABLE:
303        try:
304            app = QtWidgets.QApplication([])
305            window = CoachWindow(); window.show()
306
307            # Maintain latest_accuracy as shared variable
308            latest_accuracy = 0.0
309
310            # Connect UI signals to handlers
311            if hasattr(window, 'session_start'):
312                window.session_start.connect(handle_session_start)
313            if hasattr(window, 'session_end'):
314                # Pass latest_accuracy to session end handler
315                window.session_end.connect(lambda: handle_session_end(db, user_id, latest_accuracy, cfg))
316
317            loop = qasync.QEventLoop(app); asyncio.set_event_loop(loop)
318
319            # Run voice loop and capture latest_accuracy
320            async def run_voice_loop():
321                nonlocal latest_accuracy
322                latest_accuracy = await voice_loop(cfg, db, window, user_id, session_id)
323
324            asyncio.ensure_future(run_voice_loop())
325            with loop:
326                loop.run_forever()
327            return
328        except Exception as e:  # pragma: no cover - depends on system Qt
329            print("⚠️ Qt GUI failed to start:", e)
330            print(
331                "Install system Qt libraries (e.g. libEGL) or run in CLI mode."
332            )
333
334    ui = ConsoleUI()
335    await voice_loop(cfg, db, ui, user_id, session_id)
336
337if __name__ == "__main__":
338    asyncio.run(main())