export const FALLBACK_ANSWERS: Record<string, string> = {
  discovery: `**Summary**

Users struggle to discover new music primarily because the algorithm heavily favors familiar artists and genres they already listen to. The recommendation system creates a comfort bubble that becomes increasingly difficult to break out of, and the limited discovery surfaces beyond Discover Weekly offer few alternative pathways to unfamiliar content.

**Key pain points**

- **Algorithm echo chamber**: The recommendation engine reinforces existing listening habits rather than introducing genuinely new or unfamiliar artists
- **Limited discovery surfaces**: Beyond Discover Weekly and Release Radar, users have few dedicated pathways to explore music outside their established preferences
- **Genre lock-in**: Once a user establishes a listening pattern, the algorithm struggles to suggest content from entirely different genres or styles
- **Lack of contextual discovery**: Users want music discovery tied to moods, activities, or life moments — not just listening history

**Product focus areas**

- **Discovery diversity controls**: Build explicit user-facing controls that let listeners indicate how adventurous they want their recommendations to be
- **New artist surfaces**: Create dedicated spaces for emerging artists and genres the user has never explored
- **Serendipity mechanisms**: Introduce intentional randomness and cross-genre bridges in autoplay and radio
- **Social discovery paths**: Leverage what friends and similar listeners are discovering as a recommendation signal

**Recommended actions**

- Introduce a "discovery intensity" slider that lets users control how much novelty they want in algorithmic playlists
- Launch a dedicated "Explore" tab focused exclusively on content outside the user's established taste profile
- Add "break the loop" prompts that appear when the algorithm detects repetitive listening patterns
- Test curator-driven discovery feeds as an alternative to purely algorithmic recommendations`,

  recommendation: `**Summary**

The most common frustrations with Spotify's recommendation system center around repetitiveness and staleness. Users consistently report that recommendations cycle through the same small pool of artists, that Discover Weekly loses freshness over time, and that the algorithm fails to distinguish between casual listening and genuine preference signals.

**Key pain points**

- **Repetitive suggestions**: The same artists and tracks appear across multiple recommendation surfaces, creating a feeling of staleness
- **Signal misinterpretation**: A single play or accidental listen permanently skews recommendations, with no easy way to correct the algorithm
- **Discover Weekly decay**: Users report that Discover Weekly starts strong but becomes repetitive after several months of use
- **One-dimensional profiling**: Recommendations fail to account for different listening contexts — working out, studying, relaxing, or socializing each require different music

**Product focus areas**

- **Algorithmic freshness**: Implement decay mechanisms that rotate out previously recommended content and enforce novelty quotas
- **Intent-aware recommendations**: Distinguish between active discovery, background listening, and mood-based sessions to provide contextually appropriate suggestions
- **Feedback correction**: Make it easier for users to tell the algorithm when a recommendation was wrong without fully resetting their profile
- **Multi-taste modeling**: Build separate taste profiles for different listening moods rather than one averaged profile

**Recommended actions**

- Add visible "not interested" and "more like this" controls on every recommendation surface
- Implement a freshness constraint that prevents the same artist from appearing in recommendations more than once per week
- Build context detection that adjusts recommendations based on time of day, activity, and listening device
- Create a "recommendation reset" option for specific genres or artists without wiping the entire profile`,

  listening: `**Summary**

Users exhibit diverse listening behaviors that Spotify's current system inadequately supports. The primary listening goals range from active music discovery and mood-based selection to passive background listening and social sharing — each requiring fundamentally different algorithmic approaches and interface affordances.

**Key pain points**

- **Mode mismatch**: The app treats all listening equally, whether a user is actively exploring or passively having background music
- **Playlist management friction**: Creating, organizing, and maintaining playlists for different moods and activities is cumbersome
- **Session continuity gaps**: When users finish a playlist or album, autoplay often disrupts the established mood or energy level
- **Cross-context confusion**: Listening to a workout playlist pollutes relaxation recommendations and vice versa

**Product focus areas**

- **Listening mode detection**: Automatically detect whether users are in active discovery, passive listening, or focused work mode and adapt the experience
- **Smart session management**: Improve autoplay logic to maintain energy, mood, and genre consistency when content ends
- **Activity-based organization**: Provide better tools for organizing music by activity, mood, and context rather than just playlists
- **Separation of listening contexts**: Allow users to maintain distinct taste profiles for different listening situations

**Recommended actions**

- Implement listening "modes" that users can explicitly set (discover, focus, workout, sleep) with tailored algorithmic behavior for each
- Build smarter autoplay that analyzes the mood and tempo arc of what was played before suggesting next tracks
- Add automatic playlist organization by detected listening context
- Test "session history" that lets users revisit and save music from specific listening sessions`,

  repetition: `**Summary**

Users fall into repetitive listening patterns because the algorithm optimizes for engagement (replaying known favorites) over exploration. The comfort of familiar music combined with insufficient prompts to explore creates a self-reinforcing loop where the algorithm keeps serving what it already knows the user will accept.

**Key pain points**

- **Algorithmic reinforcement loop**: The system interprets repeated plays as strong preference signals, which leads to even more of the same content being recommended
- **Comfort over exploration**: Users default to familiar music when no compelling alternative is presented, and the app rarely challenges this behavior
- **Autoplay repetitiveness**: When users don't actively choose music, autoplay tends toward safe, already-heard tracks rather than introducing new content
- **No variety awareness**: The system lacks a mechanism to detect and break monotonous listening patterns proactively

**Product focus areas**

- **Loop detection and intervention**: Build systems that identify when users are stuck in repetitive patterns and offer gentle nudges toward new content
- **Balanced optimization**: Shift recommendation objectives from pure engagement (replays) toward a blend of satisfaction and discovery
- **Autoplay diversity**: Increase the novelty injection in autoplay and radio sessions with configurable intensity
- **Listening history awareness**: Use temporal patterns to identify when users might be open to exploring versus when they want comfort

**Recommended actions**

- Add "break the loop" notifications or playlist suggestions when repetitive patterns are detected
- Redesign autoplay to gradually introduce unfamiliar tracks mixed with familiar ones, increasing novelty over time
- Implement a "listening diversity score" visible to users that encourages exploration
- Create time-based triggers that suggest new music after a threshold of repeated content consumption`,

  segments: `**Summary**

Different user segments experience distinct discovery challenges based on their listening style, subscription tier, and engagement level. Power listeners face algorithm fatigue and echo chambers, casual users struggle with limited onboarding, free-tier users are frustrated by ad interruptions during discovery, and niche-genre enthusiasts find the mainstream-biased algorithm particularly ineffective.

**Key pain points**

- **Power listeners vs. casual users**: Heavy users exhaust recommendations quickly and need deeper catalogs, while casual users need simpler, curated entry points
- **Free vs. Premium disparity**: Free-tier users face ad interruptions that break the discovery flow and shuffle-only mode prevents intentional exploration
- **Niche genre enthusiasts**: Users with specialized taste profiles find mainstream-optimized algorithms especially poor at serving their needs
- **New users vs. long-term subscribers**: New users lack enough data for personalization, while long-term users feel locked into stale taste profiles

**Product focus areas**

- **Segment-specific onboarding**: Tailor the initial experience based on detected listening style rather than one-size-fits-all
- **Depth for power users**: Provide advanced discovery tools and deeper algorithmic exploration for heavy listeners
- **Free-tier discovery protection**: Reduce friction in the discovery experience for non-paying users to support eventual conversion
- **Genre-specialist algorithms**: Develop or tune recommendation models for underserved genre communities

**Recommended actions**

- Build listening-style segmentation into the recommendation engine and adapt surfaces per segment
- Create a "deep cuts" mode for power listeners that specifically targets less-played catalog
- Design a lighter ad experience specifically during active discovery sessions on the free tier
- Develop genre-specialist recommendation tracks for communities poorly served by the general algorithm`,

  unmet_needs: `**Summary**

The most consistently emerging unmet needs across user reviews center on meaningful personalization control, diverse discovery pathways, and transparent algorithmic behavior. Users repeatedly express wanting more agency over how the algorithm shapes their experience, rather than being passive recipients of automated recommendations.

**Key pain points**

- **Lack of user control over algorithms**: Users want to influence, adjust, and override what the recommendation engine does — not just accept its output
- **No dedicated exploration experience**: There is no space in the app designed purely for discovering unfamiliar music without algorithmic bias from past behavior
- **Poor feedback mechanisms**: Users cannot easily tell the system what went wrong with a recommendation or what direction they want to go
- **Missing social discovery features**: Users want to discover music through trusted human connections rather than algorithms alone

**Product focus areas**

- **Algorithmic transparency and control**: Give users visible levers to tune their recommendation experience and understand why content was suggested
- **Dedicated discovery space**: Build a distinct section of the app focused on exploration that operates independently from the main recommendation feed
- **Rich feedback loops**: Create intuitive ways for users to correct, refine, and direct the algorithm beyond simple like/dislike
- **Human-powered discovery**: Invest in curator, editorial, and social discovery features alongside algorithmic approaches

**Recommended actions**

- Design a "why was this recommended" explainability feature with actionable controls
- Launch a dedicated Explore section with curated discovery pathways independent of personal history
- Implement multi-signal feedback (mood, energy, context) beyond binary like/dislike
- Build community-driven discovery through taste-matched groups and trusted curator networks`,

  pricing: `**Summary**

Pricing frustrations concentrate around perceived poor value on the Premium tier relative to competitors, confusing family and student plan policies, and an excessively aggressive ad experience on the free tier that pushes users away rather than converting them.

**Key pain points**

- **Premium value perception**: Users question whether Premium offers enough beyond ad removal to justify the monthly cost
- **Ad overload on free tier**: The frequency and length of ads is perceived as punitive rather than a natural trade-off, driving users to competitors
- **Plan complexity**: Family plan verification, student eligibility requirements, and tier differences create friction
- **Price sensitivity in emerging markets**: Users in developing countries find global pricing misaligned with local purchasing power

**Product focus areas**

- **Premium differentiation**: Strengthen exclusive features (audio quality, offline, discovery tools) to justify the subscription cost
- **Free-tier ad balance**: Reduce perceived hostility of the ad experience while maintaining revenue
- **Plan simplification**: Streamline family and student verification processes and clarify tier benefits
- **Localized value propositions**: Adapt pricing and feature bundles to regional economic contexts

**Recommended actions**

- Conduct value-perception research to identify which Premium features users consider most worth paying for
- Test reduced ad frequency with longer individual ads to improve the free-tier experience without revenue loss
- Simplify plan enrollment and verification workflows
- Develop market-specific pricing tiers for regions with high churn due to cost`,

  ui_ux: `**Summary**

UI and UX frustrations revolve around navigation complexity, difficulty managing large music libraries, unintuitive playlist organization, and frequent changes to familiar interface patterns that disrupt established user workflows.

**Key pain points**

- **Navigation depth**: Key features are buried too deep in menus, requiring too many taps to reach frequently used functions
- **Library management**: Organizing saved music, albums, and playlists becomes increasingly painful as libraries grow
- **Interface instability**: Frequent redesigns and feature relocations frustrate users who had learned previous patterns
- **Discovery UX**: The path from hearing a recommendation to exploring the artist and saving content involves too much friction

**Product focus areas**

- **Information architecture**: Flatten navigation and bring frequently-used actions to more accessible positions
- **Library scalability**: Design library management tools that work well at scale — filtering, sorting, bulk operations
- **Change management**: Implement UI changes more gradually and provide clear migration paths for users
- **Exploration flow**: Reduce the number of steps between discovery and action (save, playlist add, artist dive)

**Recommended actions**

- Run usability audits on the top user flows and reduce tap-count for common actions
- Build power-user library tools (smart playlists, bulk edit, advanced search within library)
- Adopt a more gradual rollout approach for major UI changes with opt-in periods
- Streamline the "discover to save" flow to require fewer interactions`,

  performance: `**Summary**

Performance and stability concerns focus on app crashes during playback, slow loading times for library and search, Bluetooth connectivity issues, and battery drain — all of which erode trust in the core listening experience.

**Key pain points**

- **Playback interruptions**: Unexpected pauses, skips, and crashes during music playback undermine the fundamental value proposition
- **Slow load times**: Library, search results, and playlist loading feel sluggish, especially on older devices or slower connections
- **Bluetooth instability**: Connection drops and audio quality degradation over Bluetooth are a persistent complaint
- **Battery and resource consumption**: The app is perceived as resource-heavy relative to its function

**Product focus areas**

- **Playback reliability**: Invest in playback engine stability as the highest-priority technical concern
- **Performance optimization**: Reduce memory and loading times, especially for large libraries
- **Bluetooth stack improvements**: Improve codec negotiation and connection recovery for wireless audio
- **Resource efficiency**: Optimize background processes and caching to reduce battery impact

**Recommended actions**

- Establish playback reliability as a top-line engineering metric with zero-tolerance for regression
- Profile and optimize the library and search loading paths for low-end devices
- Implement better Bluetooth reconnection logic and codec fallback handling
- Reduce background activity and optimize caching strategies for battery efficiency`,

  social: `**Summary**

Users consistently express wanting richer social features that enable collaborative listening, shared discovery, and music-based connection with friends. The current social experience feels minimal compared to the richness of the music platform itself.

**Key pain points**

- **Limited collaborative features**: Group playlists and shared listening sessions feel basic and disconnected from the core experience
- **No social discovery feed**: Users cannot easily see what friends are discovering or find music through social connections
- **Sharing friction**: Sharing music to external platforms or within Spotify involves too many steps
- **Community absence**: There is no in-app community or discussion space around music, artists, or genres

**Product focus areas**

- **Collaborative listening**: Expand real-time and asynchronous shared listening experiences
- **Social discovery**: Build a feed or surface showing friend activity, shared playlists, and social recommendations
- **Frictionless sharing**: Make sharing music within and outside the app effortless
- **Community spaces**: Create spaces for discussion and connection around shared musical interests

**Recommended actions**

- Enhance collaborative playlist features with real-time activity indicators and voting
- Launch a social discovery feed showing what friends are saving and discovering
- Implement one-tap sharing to stories and messages across platforms
- Test community spaces around genres, moods, or local music scenes`,

  audio_quality: `**Summary**

Audio quality concerns span across inconsistent streaming quality, Bluetooth codec limitations, perceived differences between free and Premium tiers, and lack of transparent quality indicators. Users who care about sound fidelity feel underserved by the current offerings.

**Key pain points**

- **Quality inconsistency**: Audio quality fluctuates based on network conditions without clear user-facing indicators
- **Bluetooth codec limitations**: Wireless listening often degrades quality below what the stream provides
- **Free vs. Premium gap**: The quality difference between tiers is not always perceptible, undermining Premium's value
- **No lossless option**: Audiophile users have long requested a high-fidelity tier that has yet to materialize

**Product focus areas**

- **Quality transparency**: Show users what quality they are receiving and why, with easy controls to override
- **Bluetooth optimization**: Improve codec selection and handoff to maximize quality for wireless listeners
- **Premium audio differentiation**: Make the quality advantage of Premium more tangible and perceptible
- **Lossless roadmap**: Define and communicate a clear path toward high-fidelity streaming

**Recommended actions**

- Add a visible audio quality indicator during playback showing current bitrate and codec
- Implement intelligent Bluetooth codec selection that maximizes quality for the connected device
- Research which audio quality improvements users actually perceive and prioritize those
- Evaluate the feasibility and market demand for a lossless or hi-fi streaming tier`,

  playlist: `**Summary**

Playlist-related frustrations center on limited organizational tools, algorithmic playlists that grow stale, lack of smart playlist features, and insufficient collaboration capabilities. Users want more powerful and flexible playlist management.

**Key pain points**

- **Organization limitations**: No folders, tags, or smart filtering within playlists makes large collections unwieldy
- **Algorithmic playlist staleness**: Personalized playlists like Discover Weekly and Daily Mixes become predictable over time
- **No smart playlists**: Users cannot create rule-based playlists that automatically update based on criteria
- **Collaboration friction**: Shared playlists lack activity feeds, voting, or contribution tracking

**Product focus areas**

- **Advanced organization**: Introduce folders, tags, sorting, and search within playlist collections
- **Playlist freshness**: Ensure algorithmic playlists rotate content more aggressively and introduce novelty
- **Smart playlist rules**: Allow users to define dynamic playlists based on genre, mood, tempo, or listening history
- **Collaboration tools**: Add contributor activity, suggestion queues, and voting to shared playlists

**Recommended actions**

- Build a playlist organization system with folders, tags, and advanced sorting options
- Implement stronger freshness constraints on algorithmic playlists to prevent staleness
- Launch a "smart playlist" builder allowing rule-based automatic playlist generation
- Enhance collaborative playlists with activity feeds and democratic track selection`,

  churn: `**Summary**

The primary drivers of user churn from Spotify relate to perceived value degradation over time, recommendation fatigue, competitive alternatives offering better features, and unresolved long-standing frustrations that accumulate into switching motivation.

**Key pain points**

- **Recommendation fatigue**: Long-term users experience declining recommendation quality, making the platform feel less valuable over time
- **Competitive pull**: Rivals offering features like lossless audio, better social integration, or superior discovery attract dissatisfied users
- **Accumulated frustration**: Small persistent issues (UI changes, ad frequency, missing features) compound into switching motivation
- **Value perception decline**: Users who initially loved the service feel it has stagnated while their expectations have grown

**Product focus areas**

- **Long-term engagement**: Design features that become more valuable the longer a user stays, creating positive lock-in
- **Competitive monitoring**: Track and respond to feature gaps that competitors exploit
- **Frustration resolution**: Systematically address the most common long-standing complaints
- **Value reinforcement**: Regularly remind users of the value they receive through personalized recaps and insights

**Recommended actions**

- Build "loyalty features" that reward and deepen the experience for long-term subscribers
- Create a competitive feature parity tracker and prioritize closing critical gaps
- Implement a systematic process for resolving top user frustrations based on review volume
- Design periodic value-reinforcement touchpoints showing users their personalized listening journey`,

  satisfaction: `**Summary**

User satisfaction with Spotify is driven primarily by catalog breadth, cross-device availability, and algorithmic personalization when it works well. Dissatisfaction concentrates around discovery limitations, ad experience on free tier, and the feeling that the platform prioritizes engagement metrics over genuine user delight.

**Key pain points**

- **Discovery ceiling**: Users initially love personalization but hit a ceiling where recommendations stop feeling fresh
- **Ad experience**: Free-tier users rate satisfaction significantly lower due to intrusive ad patterns
- **Feature stagnation**: Long-term users feel the product has not evolved meaningfully in their time using it
- **Platform priorities**: Users perceive that Spotify optimizes for metrics (time spent, plays) rather than genuine enjoyment

**Product focus areas**

- **Delight-driven design**: Shift product metrics from engagement to satisfaction and discovery delight
- **Free-tier experience**: Improve the free experience enough to maintain positive sentiment while still motivating conversion
- **Innovation cadence**: Deliver visible, meaningful feature improvements that users notice and appreciate
- **User-centric metrics**: Track and optimize for user satisfaction outcomes rather than purely engagement metrics

**Recommended actions**

- Introduce satisfaction-based success metrics alongside traditional engagement metrics
- Redesign the free-tier experience to be genuinely useful while still providing Premium upgrade motivation
- Establish a visible product innovation cadence with regular feature announcements users care about
- Create feedback channels that make users feel heard and show progress on their requests`,

  sentiment: `**Summary**

Sentiment analysis across Spotify user reviews reveals a polarized landscape — users express strong positive feelings about the core music streaming experience while harboring significant frustration with discovery limitations, algorithmic behavior, and perceived lack of product evolution.

**Key pain points**

- **Positive-to-negative shift**: Users often start as enthusiastic advocates but sentiment degrades as they encounter recommendation ceilings and repetitiveness
- **Feature-specific negativity**: Certain features (shuffle, autoplay, ads) generate disproportionately negative sentiment compared to overall app rating
- **Platform fatigue**: Long-term users express growing apathy and frustration that contrasts with their initial excitement
- **Unheard feedback**: Negative sentiment is amplified when users feel their complaints are ignored over multiple years

**Product focus areas**

- **Sentiment monitoring**: Track feature-level sentiment to identify degrading experiences before they become churn signals
- **Proactive improvement**: Address consistently negative sentiment areas before they become widespread complaints
- **User voice integration**: Create visible channels where user feedback leads to tangible product changes
- **Experience freshness**: Prevent sentiment decay by continuously evolving the discovery and personalization experience

**Recommended actions**

- Implement feature-level sentiment tracking to catch degradation early
- Prioritize product improvements in areas with the most negative sentiment concentration
- Build a public roadmap or feedback loop showing how user complaints translate into product changes
- Design "re-engagement" experiences that address the specific frustrations of users showing declining sentiment`,

  offline: `**Summary**

Offline listening and download functionality generate frustration around storage management, download reliability, and the perceived limitations imposed on free-tier users. Users who rely on offline playback for commutes, travel, or poor-connectivity areas find the current experience inconsistent.

**Key pain points**

- **Download reliability**: Downloads sometimes fail silently or become unavailable without clear explanation
- **Storage management**: Users struggle to manage downloaded content within device storage constraints
- **Free-tier restrictions**: Inability to select specific tracks for offline play on the free tier frustrates users who need this for connectivity-limited situations
- **Sync inconsistency**: Downloaded playlists don't always reflect recent additions or removals

**Product focus areas**

- **Download reliability**: Ensure downloads complete reliably with clear progress indicators and error recovery
- **Smart storage management**: Build intelligent tools that help users manage offline content within their storage budget
- **Offline experience parity**: Ensure the offline listening experience feels as complete as online playback
- **Sync transparency**: Make playlist sync behavior predictable and visible to users

**Recommended actions**

- Implement robust download retry logic with clear status indicators for each track
- Build automatic storage management that prioritizes frequently-played offline content
- Add smart download suggestions based on upcoming travel or predicted connectivity gaps
- Ensure playlist changes are reflected in downloads within a predictable timeframe`,

  podcast: `**Summary**

Podcast-related feedback reveals tension between music-first users who feel podcasts dilute the experience and podcast consumers who want better discovery and management tools. The integration of podcasts into a music platform creates UX conflicts that neither audience finds ideal.

**Key pain points**

- **Unwanted podcast promotion**: Music-focused users resent podcast recommendations appearing in their music spaces
- **Discovery limitations**: Podcast discovery relies heavily on editorial curation rather than personalized algorithmic suggestions
- **Playback feature gaps**: Podcast-specific features (variable speed, chapter markers, sleep timers) feel less polished than competitors
- **Library confusion**: Mixing podcasts and music in the same library creates organizational challenges

**Product focus areas**

- **Separation of concerns**: Allow users to control how much podcast content appears in their music experience
- **Podcast-specific discovery**: Build dedicated podcast recommendation algorithms separate from music
- **Playback features**: Invest in podcast-specific playback capabilities to match dedicated podcast apps
- **Content organization**: Provide clear separation tools for users who want distinct music and podcast experiences

**Recommended actions**

- Add toggle controls that let users minimize or remove podcast suggestions from music surfaces
- Develop a dedicated podcast discovery engine separate from the music recommendation system
- Prioritize podcast playback features (speed control, chapters, smart resume) to match best-in-class competitors
- Create distinct library sections with clear navigation between music and podcast content`,

  competition: `**Summary**

Competitive pressure from alternative music streaming services creates churn risk as users compare Spotify's discovery, audio quality, pricing, and social features against rival platforms. Users frequently reference competitor advantages when expressing frustration with Spotify's limitations.

**Key pain points**

- **Discovery comparison**: Users perceive rival platforms as offering more diverse and adventurous music recommendations
- **Audio quality gap**: Competitors offering lossless or high-resolution audio make Spotify's offering seem inferior to quality-conscious listeners
- **Feature innovation pace**: Users feel competitors are innovating faster in areas like social features, lyrics, and personalization
- **Value proposition erosion**: As competitors match Spotify's catalog, the differentiating factors become less clear

**Product focus areas**

- **Discovery leadership**: Reclaim the innovation lead in music discovery and personalization
- **Quality competitiveness**: Address the audio quality gap that competitors are exploiting
- **Feature parity and beyond**: Close critical feature gaps while also innovating in unique directions
- **Unique value creation**: Build features that cannot be easily replicated by competitors

**Recommended actions**

- Conduct regular competitive analysis focused on discovery and personalization features
- Develop a clear audio quality roadmap that addresses the lossless demand
- Identify and invest in uniquely differentiating features that competitors cannot easily replicate
- Strengthen ecosystem lock-in through exclusive integrations, social features, and personalization depth`,

  recurring_issues: `**Summary**

The most frequently recurring issues reported by Spotify users center on algorithmic repetitiveness, limited music discovery pathways, intrusive advertising on the free tier, UI/UX inconsistency across updates, and degraded recommendation quality over time. These five areas represent the dominant themes that appear consistently across all review sources.

**Key pain points**

- **Algorithm repetitiveness**: Users consistently report that recommendations cycle the same small pool of artists and tracks, creating listening fatigue
- **Discovery limitations**: Beyond Discover Weekly, users lack meaningful ways to explore genuinely new and unfamiliar music
- **Ad experience on free tier**: The frequency, length, and intrusiveness of ads is the single most cited complaint from non-paying users
- **UI instability**: Frequent interface changes and feature relocations disrupt learned behaviors and frustrate long-term users
- **Recommendation decay**: Personalization quality degrades over time as the algorithm locks users into narrowing taste profiles

**Product focus areas**

- **Algorithmic diversity**: Enforce freshness and novelty constraints across all recommendation surfaces to prevent repetition
- **Discovery investment**: Build multiple independent discovery pathways (social, editorial, contextual) beyond algorithmic playlists
- **Ad experience redesign**: Reduce perceived hostility of free-tier advertising while maintaining conversion motivation
- **Interface stability**: Adopt slower, more gradual UI rollouts with user opt-in for major changes
- **Profile freshness**: Implement taste profile decay that prevents long-term users from getting trapped in stale recommendations

**Recommended actions**

- Audit the top recurring complaints quarterly and assign dedicated teams to the highest-volume issues
- Implement a "freshness score" metric for recommendations and enforce minimum thresholds
- Redesign the free-tier ad cadence to balance revenue with user tolerance
- Create a UI stability policy that limits breaking changes per release cycle`,

  improvements: `**Summary**

The highest-impact improvements Spotify should prioritize based on user feedback are: diversifying the recommendation engine, building dedicated discovery experiences, giving users control over algorithmic behavior, stabilizing the interface, and improving the free-tier experience to reduce churn.

**Key pain points**

- **No user control over algorithm**: Users cannot adjust, correct, or influence how recommendations are generated for them
- **Single discovery surface**: Discover Weekly is the only dedicated discovery feature, and it becomes stale for long-term users
- **Opaque personalization**: Users don't understand why content is recommended and cannot course-correct when it's wrong
- **Feature stagnation**: Long-term users feel the product hasn't meaningfully evolved in their time using it
- **Free-to-Premium gap**: The free experience is intentionally degraded rather than offering a compelling upgrade path

**Product focus areas**

- **User agency**: Build visible controls that let users tune recommendation intensity, diversity, and direction
- **Discovery portfolio**: Create multiple discovery surfaces (social, mood-based, editorial, serendipity) beyond a single weekly playlist
- **Transparency features**: Add explainability to recommendations so users understand and can correct algorithmic behavior
- **Innovation cadence**: Deliver regular, visible feature improvements that demonstrate platform evolution
- **Conversion through value**: Make Premium attractive through exclusive features rather than making free punitive

**Recommended actions**

- Launch user-facing recommendation controls (diversity slider, genre preferences, "not interested" feedback)
- Build a dedicated Explore section with curated discovery pathways independent of listening history
- Implement a "why this recommendation" feature with actionable correction options
- Establish a quarterly feature release cadence with user-visible improvements
- Redesign the free-to-Premium journey around added value rather than removed annoyances`,

  general: `**Summary**

Analysis of Spotify user feedback reveals that the most significant areas of concern span across music discovery limitations, recommendation repetitiveness, and insufficient user control over the algorithmic experience. Users want a more personalized, diverse, and transparent music platform.

**Key pain points**

- **Discovery limitations**: Users find it difficult to break out of their established listening patterns and discover genuinely new music
- **Recommendation staleness**: Algorithmic suggestions become repetitive over time, cycling through the same pool of artists
- **Lack of user control**: Users feel they have insufficient ability to influence or correct how the algorithm shapes their experience
- **Interface friction**: Common actions require too many steps, and frequent UI changes disrupt established workflows

**Product focus areas**

- **Discovery innovation**: Create multiple pathways to new music that don't rely solely on algorithmic history
- **Recommendation freshness**: Implement diversity and novelty constraints in the recommendation engine
- **User empowerment**: Give users visible controls over algorithmic behavior and personalization
- **Experience polish**: Reduce friction in core flows and maintain UI consistency

**Recommended actions**

- Prioritize building dedicated discovery experiences separate from the main recommendation feed
- Implement freshness constraints that prevent algorithmic staleness
- Design user-facing controls that provide transparency and agency over recommendations
- Conduct systematic UX audits on the most-used flows to reduce unnecessary friction`,
};

const INTENT_KEYWORDS: Record<string, string[]> = {
  discovery: [
    "discover", "find new", "new music", "fresh", "explore", "autoplay",
    "struggle to find", "hard to find", "can't find", "discovery",
    "music discovery", "new artist", "new genre", "unfamiliar music",
  ],
  recommendation: [
    "recommend", "suggestion", "frustrat", "algorithm", "stale", "boring",
    "same songs", "same artists", "not accurate", "irrelevant", "quality of suggest",
  ],
  listening: [
    "listening behavior", "listening habit", "listening pattern", "how do users listen",
    "trying to achieve", "music consumption", "listening goal", "use spotify",
  ],
  repetition: [
    "repeat", "same song", "same artist", "same content", "loop", "stuck",
    "over and over", "monoton", "again and again", "recycl",
  ],
  segments: [
    "segment", "user type", "different user", "who experience", "demographic",
    "persona", "power user", "casual user", "new user", "group of user",
  ],
  unmet_needs: [
    "unmet need", "what do users want", "what users need", "consistently emerge",
    "what's missing", "gap", "expectation", "wish", "desire", "demand",
    "feature request", "should add", "need to add",
  ],
  pricing: [
    "price", "premium", "subscription", "expensive", "cost", "free tier",
    "ads", "ad supported", "family plan", "student plan", "pay", "money", "worth",
  ],
  ui_ux: [
    "ui", "ux", "interface", "design", "navigation", "usability", "hard to use",
    "confusing", "layout", "menu", "button", "screen", "tap", "click",
  ],
  performance: [
    "crash", "bug", "slow", "lag", "performance", "freeze", "stability",
    "battery", "loading", "glitch", "error", "not working",
  ],
  social: [
    "social", "share", "friend", "collaborative", "together", "community",
    "group listen", "connect", "follow",
  ],
  audio_quality: [
    "audio quality", "sound quality", "bitrate", "bluetooth", "lossless",
    "hi-fi", "headphone", "speaker", "volume", "loud",
  ],
  playlist: [
    "playlist", "daily mix", "discover weekly", "release radar", "curate",
    "organize", "collection", "queue", "shuffle", "order",
  ],
  churn: [
    "churn", "leave", "cancel", "unsubscribe", "switch", "competitor",
    "stop using", "quit", "abandon", "why do users leave",
    "why users leave", "losing users", "user loss",
  ],
  satisfaction: [
    "satisf", "happy", "enjoy", "love", "hate", "rating", "review score",
    "positive", "negative", "overall experience", "how do users feel",
    "what do users like", "what works well", "strengths",
  ],
  sentiment: [
    "sentiment", "emotion", "feeling", "mood", "tone", "attitude",
    "opinion", "perception", "feedback tone",
  ],
  offline: [
    "offline", "download", "no internet", "without wifi", "storage",
    "save for later", "travel", "airplane",
  ],
  podcast: [
    "podcast", "episode", "show", "audiobook", "spoken word", "talk",
    "non-music", "content mix",
  ],
  competition: [
    "compet", "apple music", "youtube music", "tidal", "amazon music",
    "deezer", "alternative", "better than", "compared to", "vs",
  ],
};

const BROAD_PATTERNS: [RegExp, string][] = [
  [/top\s*\d*\s*(recurring|common|frequent|major|biggest|main|critical)\s*(issue|problem|complaint|pain|concern|frustration)/i, "recurring_issues"],
  [/(recurring|common|frequent|major|biggest|main)\s*(issue|problem|complaint|pain|concern|frustration)/i, "recurring_issues"],
  [/what\s*(are|is)\s*the\s*(top|main|biggest|most common|key|primary|major)/i, "recurring_issues"],
  [/(top|main|biggest|key|primary)\s*\d*\s*(issue|problem|complaint|pain|concern|challenge|frustration)/i, "recurring_issues"],
  [/most\s*(common|frequent|reported|mentioned)\s*(issue|problem|complaint|pain|concern)/i, "recurring_issues"],
  [/(improve|improvement|fix|solve|address|better|enhance)/i, "improvements"],
  [/(what should|how can|how to)\s*(spotify|they|the team|product)/i, "improvements"],
  [/(priority|prioriti|roadmap|action|next step|strategy)/i, "improvements"],
  [/(complain|complaint|negative|bad|worst|terrible|horrible|awful|poor)/i, "recurring_issues"],
  [/(feedback|review|user say|users say|people say|what are users)/i, "recurring_issues"],
  [/(trend|pattern|theme|insight|finding|observation)/i, "recurring_issues"],
  [/(engage|engagement|retention|loyalty|stick|keep user)/i, "churn"],
  [/(onboard|new user|first time|sign up|getting started)/i, "segments"],
  [/(personaliz|customiz|tailor|individual)/i, "recommendation"],
  [/(feature|functionality|capability|tool)/i, "unmet_needs"],
];

export function detectIntent(question: string): string {
  const q = question.toLowerCase();

  // First try specific keyword matching
  let bestIntent = "";
  let bestScore = 0;
  for (const [intent, keywords] of Object.entries(INTENT_KEYWORDS)) {
    const score = keywords.reduce(
      (sum, kw) => sum + (q.includes(kw) ? 3 + kw.length : 0),
      0
    );
    if (score > bestScore) {
      bestScore = score;
      bestIntent = intent;
    }
  }

  // If any topic keyword matched, use it — topic-specific answers are always better
  if (bestScore > 0 && bestIntent) return bestIntent;

  // Otherwise, try broad pattern matching for general questions
  for (const [pattern, intent] of BROAD_PATTERNS) {
    if (pattern.test(q)) return intent;
  }

  return "general";
}

export function getFallbackAnswer(question: string): string {
  const intent = detectIntent(question);
  return FALLBACK_ANSWERS[intent] || FALLBACK_ANSWERS.general;
}
