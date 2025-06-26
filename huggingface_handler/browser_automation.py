import os
from .screenshots import ScreenshotManager
from .progress import ProgressTracker
from ..shared_browser_session import SharedBrowserSessionManager

class BrowserAutomation:
    def __init__(self):
        self.screenshot_manager = ScreenshotManager()
        self.session_manager = SharedBrowserSessionManager()

    async def check_hf_access_with_playwright(self, hf_url: str,
                                              session_id: str = None):
        """
        Use Playwright to check if we have access to the HF repository and
        request access if needed.
        Returns: (has_access: bool, needs_auth: bool, 
                 error_message: str or None)
        """
        ProgressTracker.update_progress(session_id,
                                        "Checking repository access...", 15)
        
        try:
            # Ensure authentication first
            await self.session_manager.ensure_authenticated('huggingface')
            
            # Create a page using the shared session
            page = await self.session_manager.create_page('huggingface')
            
            try:
                # Check repository access
                has_access, error_msg = \
                    await self._check_repository_access_after_login(
                        page, hf_url, session_id)
                return has_access, True, error_msg
            finally:
                await page.close()
                # Save session state after use
                await self.session_manager.save_session_state('huggingface')
                
        except Exception as e:
            error_msg = f"Browser automation error: {str(e)}"
            return False, True, error_msg

    async def _check_repository_access_after_login(self, page, hf_url: str, session_id: str = None, max_attempts: int = 2):
        """Check repository access after login, with optional access request."""
        for attempt in range(1, max_attempts + 1):
            try:
                ProgressTracker.update_progress(session_id, f"Checking repository access (attempt {attempt})...", 40 + (attempt * 15))
                
                await self._navigate_with_fallback(page, hf_url, f"repository access check (attempt {attempt})")
                await self.screenshot_manager.take_screenshot(page, f"repo_access_check_attempt_{attempt}", f"Initial repository page load - {hf_url}")
                
                has_access = await self._check_page_has_access(page)
                
                if has_access:
                    ProgressTracker.update_progress(session_id, "Repository is accessible!", 70)
                    await self.screenshot_manager.take_screenshot(page, "repo_access_granted", "Repository access confirmed")
                    return True, None
                
                needs_access_request = await self._check_needs_access_request(page)
                
                if needs_access_request and attempt == 1:
                    ProgressTracker.update_progress(session_id, "Repository requires access request...", 50)
                    await self.screenshot_manager.take_screenshot(page, "repo_access_required", "Repository requires access request")
                    
                    access_requested = await self._request_repository_access(page, session_id)
                    if not access_requested:
                        await self.screenshot_manager.take_screenshot(page, "access_request_failed", "Failed to submit access request")
                        return False, "Failed to request repository access"
                    
                    ProgressTracker.update_progress(session_id, "Waiting for access approval...", 60)
                    await page.wait_for_timeout(3000)
                    continue
                
                if attempt == max_attempts:
                    await self.screenshot_manager.take_screenshot(page, "repo_access_denied_final", f"Final access check failed after {max_attempts} attempts")
                    page_content = await page.content()
                    if "404" in page_content or "not found" in page_content.lower():
                        return False, "Repository or file not found"
                    elif needs_access_request:
                        return False, "Access request submitted but not yet approved. Please try again later."
                    else:
                        return False, "Repository access denied"
                
            except Exception as e:
                await self.screenshot_manager.take_screenshot(page, f"repo_access_error_attempt_{attempt}", f"Error during access check: {str(e)}")
                if attempt == max_attempts:
                    return False, f"Error checking repository access: {str(e)}"
        return False, "Unknown error checking repository access"

    async def _check_page_has_access(self, page) -> bool:
        """Check if the current page indicates we have access to the repository/file"""
        try:
            page_content = await page.content()
            page_text = page_content.lower()
            
            access_indicators = [
                "size of remote file",
                "download",
                "view file",
                "raw file content",
                "file browser",
                "model card",
                "files and versions"
            ]
            
            for indicator in access_indicators:
                if indicator in page_text:
                    return True
            
            forbidden_indicators = [
                "403",
                "forbidden",
                "is restricted",
                "ask for access",
                "access denied",
                "you don't have access",
                "request access",
                "repository is gated",
                "accept the license"
            ]
            
            for indicator in forbidden_indicators:
                if indicator in page_text:
                    return False
            
            current_url = page.url
            if any(pattern in current_url for pattern in ["/blob/", "/resolve/", "/tree/"]):
                download_elements = await page.locator('a[href*="download"], button:has-text("Download")').count()
                if download_elements > 0:
                    return True
            
            file_list_elements = await page.locator('[class*="file"], [class*="tree"], .files-container').count()
            if file_list_elements > 0:
                return True
            
            return False
            
        except Exception as e:
            print(f"Error checking page access: {e}")
            return False

    async def _check_needs_access_request(self, page) -> bool:
        """Check if the page indicates we need to request access"""
        try:
            page_content = await page.content()
            page_text = page_content.lower()
            
            access_request_indicators = [
                "request access",
                "expand to review and access",
                "gated repository", 
                "accept license",
                "agree to terms",
                "repository access",
                "is restricted",
                "ask for access"
            ]
            
            for indicator in access_request_indicators:
                if indicator in page_text:
                    return True
            
            access_elements = await page.locator('button:has-text("Request access"), button:has-text("Expand to review"), summary:has-text("Expand to review")').count()
            if access_elements > 0:
                return True
            
            return False
            
        except Exception as e:
            print(f"Error checking access request requirement: {e}")
            return False

    async def _check_login_success(self, page) -> bool:
        """Check if login was successful by looking for indicators"""
        try:
            profile_indicators = await page.locator('a[href*="/settings"], button:has-text("Log out"), [data-testid="user-menu"], .user-menu, [aria-label*="user"], .avatar').count()
            if profile_indicators > 0:
                return True
            
            current_url = page.url.lower()
            if "login" not in current_url and "huggingface.co" in current_url:
                login_forms = await page.locator('form:has(input[type="password"]), input[name="username"], input[placeholder*="Username"], input[placeholder*="Email"]').count()
                if login_forms == 0:
                    return True
            
            return False
            
        except Exception as e:
            print(f"Error checking login success: {e}")
            return False

    async def _request_repository_access(self, page, session_id: str = None) -> bool:
        """Request access to a restricted repository"""
        try:
            ProgressTracker.update_progress(session_id, "Looking for repository home link...", 46)
            
            await self.screenshot_manager.take_screenshot(page, "before_repo_navigation", "Page before looking for repository home link")
            
            # Common patterns for repository home links on restricted pages
            repo_home_selectors = [
                'a[href*="huggingface.co/"]:has-text("huggingface.co")',
                'a[href*="huggingface.co/"]:has-text("repository")',
                'a[href*="huggingface.co/"]:has-text("model")',
                'a[href*="huggingface.co/"]:has-text("here")',
                'a[href*="huggingface.co/"][href$="/"]',  # Links ending with just the repo path
                'a[href*="huggingface.co/"][href*="/tree/main"]',
                'a[href]:has-text("Visit")',
                'a[href]:has-text("Go to")',
                '.repo-link, .repository-link'
            ]
            
            repo_home_link = None
            for selector in repo_home_selectors:
                link = page.locator(selector).first
                if await link.count() > 0:
                    repo_home_link = link
                    break
            
            # If we found a repository home link, navigate to it
            if repo_home_link:
                ProgressTracker.update_progress(session_id, "Accessing to repository...", 47)
                repo_url = await repo_home_link.get_attribute('href')
                if repo_url:
                    # Ensure it's a full URL
                    if repo_url.startswith('/'):
                        repo_url = f"https://huggingface.co{repo_url}"
                    
                    # Use specialized navigation method
                    navigation_success = await self._navigate_with_fallback(page, repo_url, "repository home page")
                    
                    if not navigation_success:
                        print(f"⚠️ Repository home navigation failed, continuing anyway")
                        # Continue execution - we might still be able to find access forms on current page
                    
                    await page.wait_for_timeout(1000)
                    
                    # Take screenshot after navigating to repo home
                    await self.screenshot_manager.take_screenshot(page, "repo_home_page", f"Repository home page: {repo_url}")
            
            # Now look for "Expand to review and access" button on the repository page
            ProgressTracker.update_progress(session_id, "Looking for access request form...", 48)
            
            expand_button = page.locator('button:has-text("Expand to review and access"), summary:has-text("Expand to review"), details:has-text("Expand to review")')
            if await expand_button.count() > 0:
                await self.screenshot_manager.take_screenshot(page, "before_expand_access", "Page before expanding access form")
                await expand_button.click()
                await page.wait_for_timeout(1000)
                await self.screenshot_manager.take_screenshot(page, "after_expand_access", "Page after expanding access form")
            
            # Fill in the access request form
            ProgressTracker.update_progress(session_id, "Filling access request form...", 50)
            
            # Name field
            name_input = page.locator('input[placeholder*="Name"], input[name*="name"], input[placeholder*="required"]').first
            if await name_input.count() > 0:
                await name_input.fill("AI Research User")
            
            # Company name (if applicable)
            company_input = page.locator('input[placeholder*="Company"], input[name*="company"]').first
            if await company_input.count() > 0:
                await company_input.fill("Research Organization")
            
            # Email field
            email_input = page.locator('input[type="email"], input[placeholder*="Email"]').first
            if await email_input.count() > 0:
                email = os.environ.get("HF_USERNAME", "")
                await email_input.fill(email)
            
            # Comments/Other field
            comments_input = page.locator('textarea[placeholder*="Comments"], textarea[name*="comment"], input[placeholder*="Other"]').first
            if await comments_input.count() > 0:
                await comments_input.fill("Requesting access for AI research and development purposes.")
            
            # Take screenshot after filling form
            await self.screenshot_manager.take_screenshot(page, "access_form_filled", "Access request form filled out")
            
            # Check required checkboxes with more specific targeting
            ProgressTracker.update_progress(session_id, "Accepting terms and conditions...", 55)
            
            # Try multiple selectors for checkboxes that need to be checked
            checkbox_selectors = [
                'input[type="checkbox"][required]',  # Required checkboxes
                'input[type="checkbox"]',  # All checkboxes as fallback
                'input[type="checkbox"][name*="terms"]',  # Terms-related checkboxes
                'input[type="checkbox"][name*="agree"]',  # Agreement checkboxes
                'input[type="checkbox"][name*="accept"]',  # Accept checkboxes
                'input[type="checkbox"][id*="terms"]',  # Terms ID checkboxes
                'input[type="checkbox"][id*="agree"]',  # Agreement ID checkboxes
                'input[type="checkbox"][id*="license"]',  # License checkboxes
            ]
            
            checkboxes_checked = 0
            
            for selector in checkbox_selectors:
                checkboxes = page.locator(selector)
                checkbox_count = await checkboxes.count()
                
                if checkbox_count > 0:
                    print(f"Found {checkbox_count} checkboxes with selector: {selector}")
                    
                    for i in range(checkbox_count):
                        checkbox = checkboxes.nth(i)
                        
                        # Check if checkbox is visible and enabled
                        try:
                            is_visible = await checkbox.is_visible()
                            is_enabled = await checkbox.is_enabled()
                            is_checked = await checkbox.is_checked()
                            
                            if is_visible and is_enabled and not is_checked:
                                # Scroll checkbox into view first
                                await checkbox.scroll_into_view_if_needed()
                                await page.wait_for_timeout(500)
                                
                                # Try to check the checkbox
                                await checkbox.check()
                                checkboxes_checked += 1
                                print(f"✅ Checked checkbox {i+1} with selector: {selector}")
                                
                                # Verify it was actually checked
                                is_now_checked = await checkbox.is_checked()
                                if not is_now_checked:
                                    print(f"⚠️ Checkbox {i+1} was not actually checked, trying click instead")
                                    await checkbox.click()
                                    
                            elif is_checked:
                                print(f"ℹ️ Checkbox {i+1} was already checked")
                            elif not is_visible:
                                print(f"⚠️ Checkbox {i+1} is not visible")
                            elif not is_enabled:
                                print(f"⚠️ Checkbox {i+1} is not enabled")
                                
                        except Exception as cb_error:
                            print(f"❌ Error handling checkbox {i+1}: {cb_error}")
                            # Try alternative approach - direct click
                            try:
                                await checkbox.scroll_into_view_if_needed()
                                await checkbox.click()
                                checkboxes_checked += 1
                                print(f"✅ Successfully clicked checkbox {i+1} as fallback")
                            except Exception as click_error:
                                print(f"❌ Fallback click also failed for checkbox {i+1}: {click_error}")
                    
                    # If we found and processed checkboxes with this selector, break
                    if checkbox_count > 0:
                        break
            
            print(f"📋 Total checkboxes processed: {checkboxes_checked}")
            
            # Take screenshot after checking boxes
            if checkboxes_checked > 0:
                await self.screenshot_manager.take_screenshot(page, "access_form_checkboxes", f"Access form with {checkboxes_checked} checkboxes checked")
            else:
                await self.screenshot_manager.take_screenshot(page, "access_form_no_checkboxes", "No checkboxes found or checked")
            
            # Submit the form - find submit button first, then scroll to it
            ProgressTracker.update_progress(session_id, "Requesting access...", 58)
            submit_button = page.locator('button:has-text("Submit"), input[type="submit"], button[type="submit"]').first
            if await submit_button.count() > 0:
                # Scroll to the submit button specifically instead of just the bottom
                await submit_button.scroll_into_view_if_needed()
                await page.wait_for_timeout(1000)  # Brief pause after scrolling
                
                # Take screenshot before submitting
                await self.screenshot_manager.take_screenshot(page, "before_submit", "Form ready for submission")
                
                await submit_button.click()
                await page.wait_for_timeout(2000)
                
                # Take screenshot after submitting
                await self.screenshot_manager.take_screenshot(page, "after_submit", "Page after form submission")
                
                # Check for success message
                success_indicators = await page.locator('text="request sent", text="submitted", text="thank you"').count()
                if success_indicators > 0:
                    ProgressTracker.update_progress(session_id, "Access request submitted successfully!", 60)
                    await self.screenshot_manager.take_screenshot(page, "submit_success", "Success message visible")
                    return True
                else:
                    # Even if no explicit success message, assume it worked if form disappeared
                    form_still_present = await page.locator('button:has-text("Submit")').count() > 0
                    if not form_still_present:
                        ProgressTracker.update_progress(session_id, "Access request appears to be submitted!", 60)
                        await self.screenshot_manager.take_screenshot(page, "submit_assumed_success", "Form disappeared, assuming success")
                        return True
                    else:
                        await self.screenshot_manager.take_screenshot(page, "submit_unclear", "Form still present, unclear if submitted")
            else:
                # If no submit button found, try scrolling to bottom as fallback
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1000)
                await self.screenshot_manager.take_screenshot(page, "no_submit_button", "No submit button found")
                return False
            
            return False
            
        except Exception as e:
            print(f"❌ Error requesting repository access: {e}")
            await self.screenshot_manager.take_screenshot(page, "access_request_exception", f"Exception during access request: {str(e)}")
            return False

    async def _navigate_with_fallback(self, page, url: str, description: str = "", timeout_primary: int = 10000, timeout_fallback: int = 5000):
        """Navigate to a URL with fallback options"""
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_primary)
            print(f"✅ Successfully navigated to {url} ({description})")
            return True
        except Exception as primary_error:
            print(f"⚠️ Primary navigation timeout/error for {url}: {primary_error}")
            
            try:
                await page.goto(url, timeout=timeout_fallback)
                await page.wait_for_timeout(2000)
                print(f"✅ Fallback navigation succeeded for {url} ({description})")
                return True
            except Exception as fallback_error:
                print(f"❌ Fallback navigation also failed for {url}: {fallback_error}")
                return False