# Client transformation photos

Drop client transformation photos for the Gallery and home page in this folder.

## Uploading from GitHub

On this branch, open this folder and use **Add file -> Upload files**, then
drag the photos in. Upload the originals; do not resize or compress them
first. Compression happens here, in a follow-up commit, so the full-quality
file stays the source.

## Before anything goes live

Every photo needs Danielle's confirmation that the client agreed to be
featured publicly. A public gallery on the site is a larger step than a
story post, so permission for one is not permission for the other.

## Wiring a photo into a page

Nothing is displayed just by living in this folder. In `gallery.html` or `index.html`, copy an existing frame inside
`.trans-grid` and point it at your file. The image fills the frame
automatically:

    <div class="trans-frame"><img src="images/transformation-02.jpg"
         alt="Describe what is in the photo" loading="lazy" decoding="async"></div>

Keep `loading="lazy"` on anything below the first row.

Alt text should describe the actual hair in the photo (length, part, finish),
not repeat a generic label. Never add a client's name.

For video, copy the `<video>` block in the first Gallery frame. It needs a
poster image and an H.264 (avc1) MP4. HEVC/H.265 will not play in Firefox or
most desktop Chrome, so re-encode phone footage before adding it.
